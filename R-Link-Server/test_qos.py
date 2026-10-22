import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.qos import (
    CommandResult,
    QoSConfig,
    QoSManager,
    QoSPolicy,
    QosCommandError,
    QOS_BACKEND,
)
from core.service_state import ServiceState
from api.qos import router


def config(**overrides):
    value = {
        "interface": "eth0",
        "upload_mbps": 20,
        "download_mbps": 100,
        "policies": [
            {
                "id": "phone",
                "label": "Phone",
                "device_id": "device-1",
                "ip": "192.168.2.10",
                "upload_mbps": 10,
                "download_mbps": 30,
                "guaranteed_upload_mbps": 1,
                "guaranteed_download_mbps": 2,
                "priority": 3,
            }
        ],
    }
    value.update(overrides)
    return QoSConfig.model_validate(value)


class FakeKernel:
    def __init__(self):
        self.manager = None
        self.commands = []
        self.ifb_exists = False
        self.ifb_alias = ""
        self.ifb_qdisc = False
        self.ingress = False
        self.root = False
        self.class_parent_drift = False
        self.qdisc_default = "ffff"
        self.extra_filter_key = False
        self.mirror_action = False
        self.foreign_child = False
        self.foreign_filter = False
        self.ifb_down = False

    def _marker_config(self):
        return self.manager._desired()[1]

    def _classes(self, dev):
        marker = self.manager._load_marker()
        if marker is None:
            return []
        if dev == "eth0" and not self.root:
            return []
        if dev != "eth0" and not self.ifb_qdisc:
            return []
        config = self._marker_config()
        direction = "upload" if dev == marker["ifb"] else "download"
        handle = marker["ifb_handle"] if direction == "upload" else marker["root_handle"]
        capacity = config.upload_mbps if direction == "upload" else config.download_mbps
        payload = [
            {"kind": "htb", "classid": handle + "1",
             "root": True,
             "parent": "root",
             "options": {"rate": capacity * 1_000_000 / 8,
                          "ceil": capacity * 1_000_000 / 8}},
            {"kind": "htb", "classid": handle + "ffff",
             "parent": handle + "1",
             "options": {"rate": 0.001 * 1_000_000 / 8,
                          "ceil": capacity * 1_000_000 / 8, "prio": 7}},
        ]
        for index, policy in enumerate(config.policies):
            if not policy.enabled:
                continue
            guarantee = policy.guaranteed_upload_mbps if direction == "upload" else policy.guaranteed_download_mbps
            maximum = policy.upload_mbps if direction == "upload" else policy.download_mbps
            maximum = capacity if maximum is None else maximum
            payload.append({"kind": "htb", "classid": handle + format(10 + index, "x"),
                            "parent": handle + "1",
                            "options": {"rate": guarantee * 1_000_000 / 8,
                                         "ceil": maximum * 1_000_000 / 8,
                                         "prio": policy.priority}})
        if self.class_parent_drift:
            payload[-1]["parent"] = handle
        return payload

    def _filters(self, dev, parent):
        marker = self.manager._load_marker()
        if marker is None:
            return []
        if dev == "eth0" and parent != marker["ingress_handle"] and not self.root:
            return []
        if dev != "eth0" and not self.ifb_qdisc:
            return []
        physical, upload, ingress = self.manager._expected_filters(self._marker_config(), marker)
        if dev == "eth0" and parent == marker["root_handle"]:
            expected = physical
        elif dev == marker["ifb"] and parent == marker["ifb_handle"]:
            expected = upload
        elif dev == "eth0" and parent == marker["ingress_handle"]:
            expected = ingress
        else:
            expected = []
        result = []
        for item in expected:
            options = {}
            if item["kind"] == "flower":
                options["keys"] = {
                    "eth_type": "ipv4" if item["protocol"] == "ip" else "ipv6",
                    item["selector"] + "_ip": item["ip"],
                }
                if self.extra_filter_key:
                    options["keys"]["dst_port"] = "443"
                if item["classid"] is not None:
                    options["classid"] = item["classid"] + ":"
            if item["redirect"] is not None:
                options["actions"] = [{"order": 1, "kind": "mirred",
                                       "mirred_action": "redirect", "direction": "egress",
                                       "to_dev": item["redirect"],
                                       "control_action": {"type": "stolen"}}]
            elif self.mirror_action:
                options["actions"] = [{"order": 1, "kind": "mirred",
                                        "mirred_action": "mirror", "direction": "egress",
                                        "to_dev": "foreign0"}]
            # Match iproute2's JSON shape: a summary row followed by a detail
            # row.  The verifier must ignore the summary and validate chain 0
            # on the actual rule.
            result.append({"kind": item["kind"], "protocol": item["protocol"],
                           "pref": item["pref"], "chain": 0})
            result.append({"kind": item["kind"], "protocol": item["protocol"],
                           "pref": item["pref"], "chain": 0, "options": options})
        if self.foreign_filter and dev == "eth0" and parent == marker["root_handle"]:
            result.append({"kind": "flower", "protocol": "ip", "pref": 999,
                           "chain": 0,
                           "options": {"keys": {"eth_type": "ipv4", "dst_ip": "192.0.2.1"},
                                       "classid": marker["root_handle"] + "ffff:"}})
        return result

    def __call__(self, argv, timeout):
        argv = list(argv)
        self.commands.append(argv)
        if argv[:4] == ["tc", "-j", "qdisc", "show"]:
            dev = argv[-1]
            if dev == "eth0":
                value = []
                if self.root:
                    value.append({
                        "kind": "htb",
                        "handle": self.manager._object_names("eth0")["root_handle"],
                        "root": True,
                        "options": {"default": self.qdisc_default},
                    })
                    if self.foreign_child:
                        value.append({
                            "kind": "pfifo_fast",
                            "handle": "10:",
                            "parent": self.manager._object_names("eth0")["root_handle"] + "1",
                        })
                if self.ingress:
                    value.append({"kind": "ingress", "handle": "ffff:", "parent": "ffff:"})
                if self.foreign_child and not self.root:
                    if not value:
                        value.append({"kind": "noqueue", "handle": "0:", "root": True})
                    value.append({
                        "kind": "pfifo_fast",
                        "handle": "10:",
                        "parent": self.manager._object_names("eth0")["root_handle"] + "1",
                    })
                if not value:
                    value.append({"kind": "noqueue", "handle": "0:", "root": True})
                return CommandResult(0, json.dumps(value))
            if self.ifb_exists and dev == self.manager._object_names("eth0")["ifb"]:
                if self.ifb_qdisc:
                    value = [{
                        "kind": "htb",
                        "handle": self.manager._object_names("eth0")["ifb_handle"],
                        "root": True,
                        "options": {"default": self.qdisc_default},
                    }]
                    if self.foreign_child:
                        value.append({
                            "kind": "pfifo_fast",
                            "handle": "10:",
                            "parent": self.manager._object_names("eth0")["ifb_handle"] + "1",
                        })
                    return CommandResult(0, json.dumps(value))
                return CommandResult(0, "[]")
            return CommandResult(0, "[]")
        if argv[:4] == ["tc", "-j", "filter", "show"]:
            parent = argv[argv.index("parent") + 1] if "parent" in argv else None
            return CommandResult(0, json.dumps(self._filters(argv[argv.index("dev") + 1], parent)))
        if argv[:4] == ["tc", "-j", "class", "show"]:
            return CommandResult(0, json.dumps(self._classes(argv[-1])))
        if argv[:5] == ["ip", "-j", "-d", "link", "show"]:
            name = argv[-1]
            if self.ifb_exists and name == self.manager._object_names("eth0")["ifb"]:
                return CommandResult(0, json.dumps([{
                    "ifname": name,
                    "ifindex": 3,
                    "ifalias": self.ifb_alias,
                    "link_type": "ifb",
                    "linkinfo": {"info_kind": "ifb"},
                    "operstate": "DOWN" if self.ifb_down else "UP",
                    "flags": [] if self.ifb_down else ["UP"],
                }]))
            if name == "eth0":
                return CommandResult(0, json.dumps([{
                    "ifname": name,
                    "ifindex": 2,
                    "link_type": "ether",
                }]))
            return CommandResult(1, "")
        if argv[:3] == ["tc", "-s", "-j"]:
            return CommandResult(0, json.dumps([{
                "kind": "htb",
                "stats2": {"bytes": 100, "drops": 2, "backlog": 4},
            }]))
        if argv[:4] == ["ip", "link", "add", "name"]:
            self.ifb_exists = True
            self.ifb_alias = ""
        elif argv[:5] == ["ip", "link", "set", "dev", self.manager._object_names("eth0")["ifb"]] and "alias" in argv:
            self.ifb_alias = argv[-1]
        elif argv[:3] == ["tc", "qdisc", "add"] and "root" in argv:
            if argv[argv.index("dev") + 1] == self.manager._object_names("eth0")["ifb"]:
                self.ifb_qdisc = True
            elif argv[argv.index("dev") + 1] == "eth0":
                self.root = True
        elif argv[:3] == ["tc", "qdisc", "add"] and "ingress" in argv:
            self.ingress = True
        elif argv[:3] == ["tc", "qdisc", "del"]:
            dev = argv[argv.index("dev") + 1]
            if argv[-1] == "root":
                if dev == "eth0":
                    self.root = False
                else:
                    self.ifb_qdisc = False
            elif argv[-1] == "ingress":
                self.ingress = False
        elif argv[:3] == ["ip", "link", "del"]:
            self.ifb_exists = False
            self.ifb_alias = ""
        return CommandResult(0, "")


def linux_manager(tmp_path, fake=None, **kwargs):
    fake = fake or FakeKernel()
    manager = QoSManager(
        ServiceState(tmp_path / "state"),
        runner=fake,
        platform_name="linux",
        env={"R_LINK_QOS_ENABLED": "true"},
        command_finder=lambda name: f"/usr/bin/{name}",
        interface_provider=lambda: [(1, "eth0")],
        privileged=True,
        **kwargs,
    )
    fake.manager = manager
    return manager, fake


def test_model_rejects_non_literal_duplicate_and_unsafe_values():
    with pytest.raises(ValueError):
        QoSPolicy(id="x", label="x", ip="client.example")
    with pytest.raises(ValueError):
        QoSPolicy(id="x", label="x", ip="224.0.0.1")
    with pytest.raises(ValueError):
        QoSPolicy(id="x", label="x", ip="192.168.2.10", upload_mbps=0)
    with pytest.raises(ValueError):
        QoSPolicy(id="x", label="x", ip="192.168.2.12", upload_mbps=10 ** 1000)
    with pytest.raises(ValueError):
        QoSConfig(
            interface="eth0",
            upload_mbps=2,
            download_mbps=2,
            policies=[
                {"id": "a", "label": "a", "ip": "192.168.2.10"},
                {"id": "b", "label": "b", "ip": "192.168.2.10"},
            ],
        )
    with pytest.raises(ValueError):
        QoSConfig(
            interface="eth0",
            upload_mbps=1,
            download_mbps=1,
            policies=[
                {"id": str(index), "label": "a", "ip": f"192.168.2.{index + 10}"}
                for index in range(10)
            ],
        )
    with pytest.raises(ValueError):
        QoSConfig(
            interface="eth0",
            upload_mbps=2,
            download_mbps=2,
            policies=[
                {"id": "same", "label": "a", "ip": "192.168.2.10"},
                {"id": "same", "label": "b", "ip": "192.168.2.11"},
            ],
        )
    with pytest.raises(ValueError):
        QoSConfig(interface="-eth0", upload_mbps=2, download_mbps=2)


def test_capability_is_unavailable_on_mac_and_does_not_execute(tmp_path):
    calls = []

    def runner(argv, timeout):
        calls.append(list(argv))
        return CommandResult(0, "[]")

    manager = QoSManager(
        ServiceState(tmp_path / "state"),
        runner=runner,
        platform_name="darwin",
        env={"R_LINK_QOS_ENABLED": "true"},
        command_finder=lambda name: "/usr/bin/" + name,
        interface_provider=lambda: [(1, "en0")],
        privileged=True,
    )
    status = manager.put_config(0, config(interface=""))
    assert status["state"] == "unavailable"
    assert status["capabilities"]["available"] is False
    assert status["capabilities"]["backend"] == QOS_BACKEND
    assert status["desired"]["revision"] == 1
    with pytest.raises(Exception) as error:
        asyncio.run(manager.apply(1))
    assert getattr(error.value, "status_code", None) == 503
    assert calls == []


def test_plan_is_fixed_argv_and_contains_bidirectional_htb_ifb_flow(tmp_path):
    manager, _ = linux_manager(tmp_path)
    commands = manager.plan(config())
    assert commands
    assert all(isinstance(item, list) for item in commands)
    assert all("sudo" not in item and "sh" not in item for item in commands for item in item)
    assert any(item[:4] == ["ip", "link", "add", "name"] and item[-2:] == ["type", "ifb"] for item in commands)
    assert any(item[:3] == ["tc", "qdisc", "add"] and "ingress" in item for item in commands)
    assert any(any(part.startswith("dst_ip") for part in item) and "192.168.2.10/32" in item for item in commands)
    assert any(any(part.startswith("src_ip") for part in item) and "192.168.2.10/32" in item for item in commands)
    assert any("1kbit" in item for item in commands if item[:2] == ["tc", "class"])


def test_apply_verifies_and_persists_active_state_then_clear_only_owned_objects(tmp_path):
    manager, fake = linux_manager(tmp_path)
    manager.put_config(0, config())
    status = asyncio.run(manager.apply(1))
    assert status["state"] == "active"
    assert status["applied"]["revision"] == 1
    assert status["cleanup_revision"] == 1
    assert status["statistics"]["download"]["bytes"] == 100
    assert status["statistics"]["upload"]["drops"] == 2
    assert fake.ifb_exists and fake.root and fake.ingress
    status = asyncio.run(manager.clear_applied(1))
    assert status["state"] == "pending"
    assert status["applied"] is None
    assert status["cleanup_revision"] is None
    assert not fake.ifb_exists and not fake.root and not fake.ingress
    assert any(command[:3] == ["tc", "qdisc", "del"] for command in fake.commands)


def test_apply_same_verified_revision_is_idempotent_and_clear_revision_is_guarded(tmp_path):
    manager, fake = linux_manager(tmp_path)
    manager.put_config(0, config())
    first = asyncio.run(manager.apply(1))
    mutating = lambda: [command for command in fake.commands if (
        command[:3] in (["ip", "link", "add"], ["ip", "link", "set"], ["ip", "link", "del"],
                        ["tc", "qdisc", "add"], ["tc", "qdisc", "del"],
                        ["tc", "class", "replace"], ["tc", "filter", "replace"]))]
    mutation_count = len(mutating())
    second = asyncio.run(manager.apply(1))
    assert second["state"] == "active"
    assert len(mutating()) == mutation_count
    with pytest.raises(Exception) as error:
        asyncio.run(manager.clear_applied(2))
    assert getattr(error.value, "status_code", None) == 409
    assert len(mutating()) == mutation_count
    cleared = asyncio.run(manager.clear_applied(1))
    assert cleared["cleanup_revision"] is None
    # A fully-cleared source is safe to retry, regardless of the old revision.
    assert asyncio.run(manager.clear_applied(1))["applied"] is None


@pytest.mark.parametrize("drift", ("class_parent", "qdisc_default", "filter_key", "mirror_action", "foreign_child", "ifb_down"))
def test_active_status_rejects_semantic_kernel_drift(tmp_path, drift):
    manager, fake = linux_manager(tmp_path)
    manager.put_config(0, config())
    assert asyncio.run(manager.apply(1))["state"] == "active"
    if drift == "class_parent":
        fake.class_parent_drift = True
    elif drift == "qdisc_default":
        fake.qdisc_default = "0"
    elif drift == "filter_key":
        fake.extra_filter_key = True
    elif drift == "mirror_action":
        fake.mirror_action = True
    elif drift == "foreign_child":
        fake.foreign_child = True
    else:
        fake.ifb_down = True
    assert manager.status()["state"] == "error"


def test_external_root_qdisc_is_a_fail_closed_conflict(tmp_path):
    manager, fake = linux_manager(tmp_path)

    def external_root(argv, timeout):
        fake.commands.append(list(argv))
        if list(argv)[:4] == ["tc", "-j", "qdisc", "show"]:
            return CommandResult(0, json.dumps([{"kind": "fq_codel", "handle": "1:", "root": True}]))
        if list(argv)[:4] == ["tc", "-j", "filter", "show"]:
            return CommandResult(0, "[]")
        return CommandResult(0, "")

    manager._runner = external_root
    manager.put_config(0, config())
    with pytest.raises(Exception) as error:
        asyncio.run(manager.apply(1))
    assert getattr(error.value, "status_code", None) == 409
    assert not any(command[:3] == ["ip", "link", "add"] for command in fake.commands)


def test_preflight_rejects_foreign_child_qdisc_before_mutation(tmp_path):
    manager, fake = linux_manager(tmp_path)
    fake.foreign_child = True
    manager.put_config(0, config())
    with pytest.raises(Exception) as error:
        asyncio.run(manager.apply(1))
    assert getattr(error.value, "status_code", None) == 409
    assert not any(command[:3] == ["ip", "link", "add"] for command in fake.commands)
    assert not any(command[:3] == ["tc", "qdisc", "add"] for command in fake.commands)


def test_cleanup_preserves_marker_when_unconfirmed_flag_object_exists(tmp_path):
    manager, fake = linux_manager(tmp_path)
    manager.put_config(0, config())
    assert asyncio.run(manager.apply(1))["state"] == "active"
    marker = manager._load_marker()
    assert marker is not None
    marker["phase"] = "applying"
    marker["root_created"] = False
    manager._save_marker(marker)
    with pytest.raises(QosCommandError) as error:
        manager._remove_owned(marker)
    assert error.value.code == "ownership_unconfirmed"
    persisted = manager._load_marker()
    assert persisted is not None and persisted["root_created"] is False
    assert fake.root is True


def test_cleanup_checkpoint_can_resume_after_ingress_delete_failure(tmp_path):
    manager, fake = linux_manager(tmp_path)
    manager.put_config(0, config())
    assert asyncio.run(manager.apply(1))["state"] == "active"
    original_runner = fake
    failed = {"value": False}

    def fail_ingress_once(argv, timeout):
        if list(argv) == ["tc", "qdisc", "del", "dev", "eth0", "ingress"] and not failed["value"]:
            failed["value"] = True
            return CommandResult(1, "", "test failure")
        return original_runner(argv, timeout)

    manager._runner = fail_ingress_once
    with pytest.raises(Exception):
        asyncio.run(manager.clear_applied(1))
    checkpoint = manager._load_marker()
    assert checkpoint is not None
    assert checkpoint["phase"] == "cleanup"
    assert checkpoint["root_created"] is False
    assert checkpoint["ingress_created"] is True
    assert manager._applied() is not None
    manager._runner = fake
    cleared = asyncio.run(manager.clear_applied(1))
    assert cleared["applied"] is None
    assert manager._load_marker() is None
    assert not fake.root and not fake.ingress and not fake.ifb_exists


def test_cleanup_retry_rejects_foreign_filter_before_delete(tmp_path):
    manager, fake = linux_manager(tmp_path)
    manager.put_config(0, config())
    assert asyncio.run(manager.apply(1))["state"] == "active"
    root_handle = manager._object_names("eth0")["root_handle"]
    failed = {"value": False}

    def fail_root_once(argv, timeout):
        if list(argv) == ["tc", "qdisc", "del", "dev", "eth0",
                          "handle", root_handle, "root"] and not failed["value"]:
            failed["value"] = True
            return CommandResult(1, "", "test failure")
        return fake(argv, timeout)

    manager._runner = fail_root_once
    with pytest.raises(Exception):
        asyncio.run(manager.clear_applied(1))
    checkpoint = manager._load_marker()
    assert checkpoint is not None and checkpoint["phase"] == "cleanup"
    assert checkpoint["root_created"] is True

    fake.foreign_filter = True
    manager._runner = fake
    command_count = len(fake.commands)
    with pytest.raises(Exception):
        asyncio.run(manager.clear_applied(1))
    assert not any(command[:3] == ["tc", "qdisc", "del"] for command in fake.commands[command_count:])
    persisted = manager._load_marker()
    assert persisted is not None and persisted["root_created"] is True


def test_revision_mismatch_is_rejected_and_api_preserves_auth_and_contract(tmp_path, monkeypatch):
    monkeypatch.delenv("R_LINK_API_TOKEN", raising=False)
    manager, _ = linux_manager(tmp_path)
    app = FastAPI()
    app.include_router(router)
    app.state.services = SimpleNamespace(qos=manager, ready=True)
    with TestClient(app, base_url="http://localhost:8210", client=("127.0.0.1", 55555)) as client:
        response = client.put("/api/qos/config", json={"expected_revision": 1, "config": config().model_dump(mode="json")})
        assert response.status_code == 409
        response = client.get("/api/qos/status")
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= {"capabilities", "desired", "applied", "state", "error", "cleanup_revision", "statistics"}
        assert body["capabilities"]["backend"] == QOS_BACKEND
        assert client.delete("/api/qos/applied").status_code == 422
        assert client.get("/api/qos/status", headers={"Origin": "https://evil.invalid"}).status_code == 401
