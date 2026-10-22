"""Opt-in real Linux HTB/IFB acceptance in disposable network namespaces.

Requires root, iproute2 and iperf3. No existing interface, route, firewall or
qdisc is changed: a client, gateway and upstream are created for this test.
"""
import asyncio
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv('R_LINK_RUN_QOS_INTEGRATION') != '1',
    reason='Opt-in real Linux network namespace QoS integration',
)


def command(*argv, timeout=20):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=timeout, check=False)
    assert result.returncode == 0, f'{argv}: {result.stderr[-2000:]}'
    return result.stdout


def ns(namespace, *argv, **kwargs):
    return command('ip', 'netns', 'exec', namespace, *argv, **kwargs)


def iperf(namespace, address, source, *, reverse=False, port=5201, duration=5):
    argv = ['ip', 'netns', 'exec', namespace, 'iperf3', '-c', address,
            '-B', source, '-p', str(port), '-t', str(duration), '-O', '1', '-J']
    if reverse:
        argv.append('-R')
    return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def result_mbps(process):
    output, error = process.communicate(timeout=20)
    assert process.returncode == 0, (error[-2000:], output[-4000:])
    data = json.loads(output)
    assert 'error' not in data, data.get('error')
    return data['end']['sum_received']['bits_per_second'] / 1e6


async def gateway_scenario(state_root, client_namespace, server_namespace):
    """Runs inside the disposable gateway network namespace."""
    from core.qos import CommandResult, QoSConfig, QoSManager, _default_runner
    from core.service_state import ServiceState
    from fastapi import HTTPException

    trace = []
    def diagnostic_runner(argv, timeout):
        result = _default_runner(argv, timeout)
        trace.append({'argv':list(argv),'code':result.returncode,
                      'stdout':result.stdout[:12000],'stderr':result.stderr[:2000]})
        del trace[:-40]
        return result
    manager = QoSManager(ServiceState(state_root), runner=diagnostic_runner)
    assert manager.capabilities()['available'], manager.capabilities()
    base = {
        'interface': 'lan0', 'upload_mbps': 10, 'download_mbps': 10,
        'policies': [{
            'id': 'device-a', 'label': 'Disposable client A', 'ip': '10.77.0.2',
            'enabled': True, 'upload_mbps': 3, 'download_mbps': 2,
            'guaranteed_upload_mbps': .2, 'guaranteed_download_mbps': .2,
            'priority': 3,
        }, {
            'id': 'device-v6', 'label': 'Disposable IPv6 client', 'ip': 'fd77::2',
            'enabled': True, 'upload_mbps': 3, 'download_mbps': 2,
            'guaranteed_upload_mbps': .2, 'guaranteed_download_mbps': .2,
            'priority': 3,
        }],
    }
    assert manager.status()['applied'] is None
    saved = manager.put_config(0, QoSConfig.model_validate(base))
    revision = saved['desired']['revision']
    assert saved['applied'] is None
    try:
        applied = await manager.apply(revision)
    except HTTPException as error:
        raise AssertionError(json.dumps({'status':manager.status(),'commands':trace[-25:]})) from error
    assert applied['state'] == 'active', applied
    assert applied['applied']['revision'] == revision
    # ARP and IPv6 neighbour discovery still work after shaping is installed.
    ns(client_namespace, 'ping', '-c', '1', '-W', '3', '10.88.0.2')
    ns(client_namespace, 'ping', '-6', '-c', '1', '-W', '3', 'fd88::2')
    measured = {}
    # Each measurement gets its own server: an iperf3 server may still be
    # closing the previous control connection when the next client starts.
    for label, target, source, port in [('ipv4', '10.88.0.2', '10.77.0.2', 5201),
                                        ('ipv6', 'fd88::2', 'fd77::2', 5203)]:
        down = result_mbps(iperf(client_namespace, target, source, reverse=True, port=port))
        up = result_mbps(iperf(client_namespace, target, source, port=port + 1))
        assert .5 < down < 2.6, (label, 'download', down)
        assert .7 < up < 3.8, (label, 'upload', up)
        measured[label] = {'download_mbps': round(down, 3), 'upload_mbps': round(up, 3)}
    # Restarting the manager does not trust only the persisted database.
    restarted = QoSManager(ServiceState(state_root))
    await restarted.recover()
    assert restarted.status()['state'] == 'active'
    # External default and classifier changes must invalidate active status,
    # even while qdisc handles and class rates remain unchanged.
    marker = restarted._load_marker()
    root = marker['root_handle']
    parsed_base = QoSConfig.model_validate(base)
    def rebuild_download_tree(default):
        # HTB does not support changing qdisc options in place on all kernels.
        # Recreate only this disposable tree with the same handles/classes.
        command('tc', 'qdisc', 'del', 'dev', 'lan0', 'handle', root, 'root')
        for argv in restarted._class_commands(
                'lan0', root, root, parsed_base.download_mbps, 'download', parsed_base.policies):
            if 'default' in argv:
                argv = list(argv)
                argv[argv.index('default') + 1] = default
            command(*argv)
        for index, policy in enumerate(parsed_base.policies):
            command(*restarted._filter_command(
                'lan0', root, policy, index, destination=True,
                class_handle=root + format(10 + index, 'x')))
    rebuild_download_tree('0')
    assert restarted.status()['state'] == 'error', 'Changed default class still reported active'
    rebuild_download_tree('ffff')
    assert restarted.status()['state'] == 'active'
    original_filter = restarted._filter_command(
        'lan0', root, parsed_base.policies[0], 0,
        destination=True, class_handle=root + 'a')
    for extra in (['ip_proto', 'tcp', 'dst_port', '443'],
                  ['action', 'mirred', 'egress', 'mirror', 'dev', marker['ifb']]):
        command('tc', 'filter', 'del', 'dev', 'lan0', 'parent', root,
                'protocol', 'ip', 'pref', '100')
        command(*(original_filter + extra))
        assert restarted.status()['state'] == 'error', 'Changed classifier still reported active'
        command('tc', 'filter', 'del', 'dev', 'lan0', 'parent', root,
                'protocol', 'ip', 'pref', '100')
        command(*original_filter)
        assert restarted.status()['state'] == 'active'
    # The source generation guard is a persisted optimistic revision.
    with pytest.raises(HTTPException) as stale:
        await restarted.apply(revision - 1)
    assert stale.value.status_code == 409
    # Under competition, a high priority class borrows surplus before a low
    # priority class. Application payload rates also include protocol overhead.
    competitive = {
        'interface': 'lan0', 'upload_mbps': 6, 'download_mbps': 6,
        'policies': [{
            'id': 'high', 'label': 'High priority client', 'ip': '10.77.0.2',
            'enabled': True, 'upload_mbps': None, 'download_mbps': None,
            'guaranteed_upload_mbps': .2, 'guaranteed_download_mbps': .2, 'priority': 0,
        }, {
            'id': 'low', 'label': 'Low priority client', 'ip': '10.77.0.3',
            'enabled': True, 'upload_mbps': None, 'download_mbps': None,
            'guaranteed_upload_mbps': .2, 'guaranteed_download_mbps': .2, 'priority': 7,
        }],
    }
    saved = restarted.put_config(revision, QoSConfig.model_validate(competitive))
    revision = saved['desired']['revision']
    assert saved['state'] == 'pending'
    assert (await restarted.apply(revision))['state'] == 'active'
    high_process = iperf(client_namespace, '10.88.0.2', '10.77.0.2', reverse=True, port=5301, duration=7)
    low_process = iperf(client_namespace, '10.88.0.2', '10.77.0.3', reverse=True, port=5302, duration=7)
    high, low = result_mbps(high_process), result_mbps(low_process)
    assert high > low * 2 and high > 3 and low > .1 and high + low < 6.6, (high, low)
    measured['competition'] = {'high_mbps': round(high, 3), 'low_mbps': round(low, 3)}
    # Kernel class drift must invalidate the previously verified active status.
    classes = json.loads(command('tc', '-j', 'class', 'show', 'dev', 'lan0'))
    leaf = next(item for item in classes if item.get('parent') and (item.get('options') or item).get('prio') == 7
                and item.get('handle', '').split(':')[-1] != 'ffff')
    command('tc', 'class', 'change', 'dev', 'lan0', 'classid', leaf['handle'],
            'htb', 'rate', '200kbit', 'ceil', '300kbit', 'prio', '7')
    assert restarted.status()['state'] == 'error', 'Changed kernel class still reported active'
    # A transient deletion failure leaves a cleanup checkpoint. Foreign
    # classes added before retry must be preserved until the operator removes
    # them, rather than being deleted with the service-owned root.
    original_runner = restarted._runner
    failed_once = False
    def fail_root_delete_once(argv, timeout):
        nonlocal failed_once
        if not failed_once and list(argv[:3]) == ['tc', 'qdisc', 'del'] and 'lan0' in argv:
            failed_once = True
            return CommandResult(1, '', 'Injected disposable test failure')
        return original_runner(argv, timeout)
    restarted._runner = fail_root_delete_once
    with pytest.raises(HTTPException):
        await restarted.clear_applied(revision)
    marker = restarted._load_marker()
    assert marker['phase'] == 'cleanup'
    foreign_class = marker['root_handle'] + 'abcd'
    command('tc', 'class', 'add', 'dev', 'lan0', 'parent', marker['root_handle'] + '1',
            'classid', foreign_class, 'htb', 'rate', '100kbit', 'ceil', '100kbit')
    with pytest.raises(HTTPException):
        await restarted.clear_applied(revision)
    assert any(item.get('handle') == foreign_class for item in
               json.loads(command('tc', '-j', 'class', 'show', 'dev', 'lan0')))
    command('tc', 'class', 'del', 'dev', 'lan0', 'classid', foreign_class)
    restarted._runner = original_runner
    cleared = await restarted.clear_applied()
    assert cleared['applied'] is None, cleared
    after = result_mbps(iperf(client_namespace, '10.88.0.2', '10.77.0.2', reverse=True, port=5401, duration=3))
    assert after > 12, after
    measured['after_disable_mbps'] = round(after, 3)
    # An unrelated non-default qdisc is left intact when applying is rejected.
    command('tc', 'qdisc', 'add', 'dev', 'lan0', 'root', 'handle', '1234:', 'netem', 'delay', '1ms')
    with pytest.raises(HTTPException) as conflict:
        await restarted.apply(revision)
    assert conflict.value.status_code == 409
    roots = json.loads(command('tc', '-j', 'qdisc', 'show', 'dev', 'lan0'))
    assert any(item.get('handle') == '1234:' and item.get('kind') == 'netem' for item in roots)
    print(json.dumps({'real_kernel': True, 'measurements': measured}), flush=True)


def test_real_linux_gateway_bidirectional_limits_and_qos(tmp_path, monkeypatch):
    if platform.system() != 'Linux' or os.geteuid() != 0:
        pytest.skip('Linux root is required for disposable network namespaces')
    for binary in ('ip', 'tc', 'iperf3'):
        if not shutil.which(binary):
            pytest.fail(f'Install {binary} before opting into QoS acceptance')
    identifier = uuid.uuid4().hex[:8]
    gateway, client, upstream = (f'rlq-{part}-{identifier}' for part in ('g', 'c', 's'))
    created, servers = [], []
    try:
        for name in (gateway, client, upstream):
            command('ip', 'netns', 'add', name)
            created.append(name)
            ns(name, 'ip', 'link', 'set', 'lo', 'up')
        command('ip', 'link', 'add', 'lc' + identifier, 'type', 'veth', 'peer', 'name', 'lg' + identifier)
        command('ip', 'link', 'set', 'lc' + identifier, 'netns', client)
        command('ip', 'link', 'set', 'lg' + identifier, 'netns', gateway)
        ns(client, 'ip', 'link', 'set', 'lc' + identifier, 'name', 'eth0')
        ns(gateway, 'ip', 'link', 'set', 'lg' + identifier, 'name', 'lan0')
        command('ip', 'link', 'add', 'wg' + identifier, 'type', 'veth', 'peer', 'name', 'ws' + identifier)
        command('ip', 'link', 'set', 'wg' + identifier, 'netns', gateway)
        command('ip', 'link', 'set', 'ws' + identifier, 'netns', upstream)
        ns(gateway, 'ip', 'link', 'set', 'wg' + identifier, 'name', 'wan0')
        ns(upstream, 'ip', 'link', 'set', 'ws' + identifier, 'name', 'eth0')
        for name, interface, ipv4, ipv6 in (
            (client, 'eth0', '10.77.0.2/24', 'fd77::2/64'),
            (gateway, 'lan0', '10.77.0.1/24', 'fd77::1/64'),
            (gateway, 'wan0', '10.88.0.1/24', 'fd88::1/64'),
            (upstream, 'eth0', '10.88.0.2/24', 'fd88::2/64'),
        ):
            ns(name, 'ip', 'link', 'set', interface, 'up')
            ns(name, 'ip', 'addr', 'add', ipv4, 'dev', interface)
            ns(name, 'ip', '-6', 'addr', 'add', ipv6, 'dev', interface, 'nodad')
        ns(client, 'ip', 'addr', 'add', '10.77.0.3/24', 'dev', 'eth0')
        ns(client, 'ip', 'route', 'add', '10.88.0.0/24', 'via', '10.77.0.1')
        ns(upstream, 'ip', 'route', 'add', '10.77.0.0/24', 'via', '10.88.0.1')
        ns(client, 'ip', '-6', 'route', 'add', 'fd88::/64', 'via', 'fd77::1')
        ns(upstream, 'ip', '-6', 'route', 'add', 'fd77::/64', 'via', 'fd88::1')
        ns(gateway, 'sysctl', '-q', '-w', 'net.ipv4.ip_forward=1')
        ns(gateway, 'sysctl', '-q', '-w', 'net.ipv6.conf.all.forwarding=1')
        for port in (5201, 5202, 5203, 5204, 5301, 5302, 5401):
            servers.append(subprocess.Popen(['ip', 'netns', 'exec', upstream,
                                             'iperf3', '-s', '-p', str(port)],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(40):
            if ':5202' in ns(upstream, 'ss', '-ltn'):
                break
            time.sleep(.05)
        environment = dict(os.environ, R_LINK_QOS_ENABLED='true')
        worker = subprocess.run(['ip', 'netns', 'exec', gateway, sys.executable,
                                 str(Path(__file__).resolve()), '--gateway-scenario',
                                 str(tmp_path / 'state'), client, upstream],
                                env=environment, capture_output=True, text=True, timeout=180)
        assert worker.returncode == 0, worker.stdout + worker.stderr
        assert json.loads(worker.stdout.strip().splitlines()[-1])['real_kernel'] is True
        print(worker.stdout.strip())
    finally:
        for process in servers:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for name in reversed(created):
            subprocess.run(['ip', 'netns', 'del', name], capture_output=True, timeout=10)


if __name__ == '__main__' and len(sys.argv) == 5 and sys.argv[1] == '--gateway-scenario':
    asyncio.run(gateway_scenario(sys.argv[2], sys.argv[3], sys.argv[4]))
