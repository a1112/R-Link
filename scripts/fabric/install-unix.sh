#!/bin/sh
set -eu
if [ "$(id -u)" -ne 0 ]; then
    echo 'Installing the R-Link network service requires local administrator authentication.'
    exec sudo -- "$0" "$@"
fi
if [ "$#" -ne 3 ]; then
    echo 'Usage: install-unix.sh PAYLOAD_DIRECTORY MANIFEST_SHA256 PYTHON_PATH' >&2
    exit 2
fi
task_payload="$1"
task_manifest_hash="$2"
task_python="$3"
task_platform="$(uname -s)"
case "$task_platform" in
    Darwin) task_service="com.rlink.fabric" ;;
    Linux) task_service="r-link-fabric.service" ;;
    *) echo 'Unsupported platform.' >&2; exit 2 ;;
esac
task_destination=/usr/local/libexec/r-link
task_state=/var/lib/r-link-agent
task_lock=/var/run/r-link-fabric-install.lock
if ! mkdir "$task_lock" 2>/dev/null; then
    echo 'Another or unfinished R-Link network installation is present.' >&2
    exit 1
fi
trap 'rmdir "$task_lock"' EXIT
"$task_python" - "$task_payload" "$task_manifest_hash" "$task_platform" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]);expected=sys.argv[2];platform=sys.argv[3]
assert len(expected)==64 and hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest()==expected,'Manifest checksum mismatch'
m=json.loads((p/'manifest.json').read_text())
assert m.get('schema_version')==1 and m.get('platform')==({'Darwin':'darwin-arm64','Linux':'linux-amd64'}[platform]),'Wrong package platform'
for name in ('rlink-agent','decrypt-enrollment.py'):
 assert hashlib.sha256((p/name).read_bytes()).hexdigest()==m['files'][name],'Package checksum mismatch'
for location in ('/usr/local/libexec/r-link','/var/lib/r-link-agent'):
 assert not pathlib.Path(location).is_symlink(),'Installation path must not be a symlink'
existing=pathlib.Path('/var/lib/r-link-agent/config.json')
if existing.exists():
 assert json.loads(existing.read_text())['control_url']=='https://175.178.16.90/r-link','Existing network identity was preserved'
if platform=='Darwin':
 import plistlib
 service=pathlib.Path('/Library/LaunchDaemons/com.rlink.fabric.plist')
 if service.exists():
  expected=['/usr/local/libexec/r-link/rlink-agent','run','--config','/var/lib/r-link-agent/config.json','--udp-port','51822']
  assert plistlib.loads(service.read_bytes()).get('ProgramArguments')==expected,'Unrelated service or network configuration preserved'
else:
 service=pathlib.Path('/etc/systemd/system/r-link-fabric.service')
 if service.exists():
  commands=[line.strip() for line in service.read_text().splitlines() if line.startswith('ExecStart=')]
  assert commands==['ExecStart=/usr/local/libexec/r-link/rlink-agent run --config /var/lib/r-link-agent/config.json --udp-port 51822'],'Unrelated service or network configuration preserved'
PY
mkdir -p "$task_destination" "$task_state"
chown root "$task_destination" "$task_state"
chmod 755 "$task_destination" "$task_state"
if [ "$task_platform" = Darwin ]; then
    launchctl bootout system/com.rlink.fabric >/dev/null 2>&1 || true
else
    systemctl stop r-link-fabric.service >/dev/null 2>&1 || true
fi
install -m 755 "$task_payload/rlink-agent" "$task_destination/rlink-agent"
if [ ! -f "$task_state/config.json" ]; then
    "$task_python" - "$task_payload" "$task_destination/rlink-agent" "$task_state/config.json" <<'PY'
import json,pathlib,subprocess,sys
p=pathlib.Path(sys.argv[1]);exe=sys.argv[2];config=sys.argv[3]
result=subprocess.run([sys.executable,str(p/'decrypt-enrollment.py')],capture_output=True,text=True,timeout=10)
assert result.returncode==0,'Enrollment package validation failed'
data=json.loads(result.stdout)
assert data['control_url']=='https://175.178.16.90/r-link','Unexpected control service'
result=subprocess.run([exe,'enroll','--server',data['control_url'],'--name',data['device'],'--token-stdin','--config',config],input=data['enrollment_token']+'\n',text=True,timeout=30)
assert result.returncode==0,'Enrollment failed'
PY
else
    "$task_python" - "$task_state/config.json" <<'PY'
import json,pathlib,sys
assert json.loads(pathlib.Path(sys.argv[1]).read_text())['control_url']=='https://175.178.16.90/r-link','Existing network identity was preserved'
PY
fi
chmod 600 "$task_state/config.json"
chown root "$task_state/config.json"
if [ "$task_platform" = Darwin ]; then
    cat >/Library/LaunchDaemons/com.rlink.fabric.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.rlink.fabric</string>
<key>ProgramArguments</key><array><string>/usr/local/libexec/r-link/rlink-agent</string><string>run</string><string>--config</string><string>/var/lib/r-link-agent/config.json</string><string>--udp-port</string><string>51822</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>ThrottleInterval</key><integer>5</integer>
</dict></plist>
PLIST
    chown root:wheel /Library/LaunchDaemons/com.rlink.fabric.plist
    chmod 644 /Library/LaunchDaemons/com.rlink.fabric.plist
    plutil -lint /Library/LaunchDaemons/com.rlink.fabric.plist
    launchctl bootstrap system /Library/LaunchDaemons/com.rlink.fabric.plist
else
    cat >/etc/systemd/system/r-link-fabric.service <<'UNIT'
[Unit]
Description=R-Link encrypted virtual network
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
ExecStart=/usr/local/libexec/r-link/rlink-agent run --config /var/lib/r-link-agent/config.json --udp-port 51822
Restart=on-failure
RestartSec=5
UMask=0077
[Install]
WantedBy=multi-user.target
UNIT
    chmod 644 /etc/systemd/system/r-link-fabric.service
    systemctl daemon-reload
    systemctl enable --now r-link-fabric.service
fi
echo 'R-Link agent installed. Checking the real tunnel status...'
task_attempt=0
while [ "$task_attempt" -lt 180 ]; do
    if "$task_destination/rlink-agent" status --json 2>/dev/null | "$task_python" -c 'import json,sys; s=json.load(sys.stdin);sys.exit(0 if s.get("mode")=="vpn" and s.get("control",{}).get("connected") and s.get("tun",{}).get("ready") else 1)'; then
        "$task_destination/rlink-agent" status --json
        echo 'The tunnel exists. Peer handshakes and service connectivity require separate verification.'
        exit 0
    fi
    task_attempt=$((task_attempt+1))
    sleep 1
done
echo 'Agent installed; the real tunnel is not ready. Inspect the public status.' >&2
exit 1
