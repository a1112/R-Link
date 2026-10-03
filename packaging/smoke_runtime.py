"""Exercise the frozen server with no Python on PATH and an empty working directory."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "artifacts/payload/runtime/r-link-server.exe"
with socket.socket() as port_selection:
    port_selection.bind(("127.0.0.1", 0))
    PORT = port_selection.getsockname()[1]
BASE = f"http://127.0.0.1:{PORT}"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch(path, method="GET", headers=None):
    request = urllib.request.Request(BASE + path, method=method, headers=headers or {})
    with OPENER.open(request, timeout=15) as response:
        return json.load(response)


def main():
    with socket.socket() as check:
        if check.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"Port {PORT} is occupied; no existing process was touched")
    session = secrets.token_hex(24)
    results = {"productId": "r-link", "runtime": str(EXE), "checks": []}
    with tempfile.TemporaryDirectory(prefix="r-link-clean-smoke-") as directory:
        data = Path(directory)
        environment = os.environ.copy()
        environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        environment["R_LINK_USER_ROOT"] = str(data)
        environment.pop("R_FONT_ADMIN_KEY", None)
        environment.pop("R_LINK_API_TOKEN", None)
        environment["RBOX_DESKTOP_SESSION"] = session
        environment["RBOX_DESKTOP_PARENT"] = str(os.getpid())
        environment["RBOX_DESKTOP_PORT"] = str(PORT)
        with (data / "server-output.log").open("wb") as output:
            process = subprocess.Popen([str(EXE)], cwd=data, env=environment,
                stdout=output, stderr=subprocess.STDOUT, creationflags=0x08000000)
            try:
                deadline = time.monotonic() + 50
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError((data / "server-output.log").read_text(encoding="utf-8", errors="replace"))
                    try:
                        health = fetch("/rbox/health")
                        if health == {"status": "healthy", "service": "r-link", "session": session}:
                            break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.2)
                else:
                    raise RuntimeError("Frozen server did not become ready")
                results["checks"].append("frozen-server-health-without-python-or-source-cwd")
                try:
                    fetch("/rbox/shutdown", "POST", {"x-rbox-session": "another-instance"})
                    raise AssertionError("Shutdown accepted a foreign instance")
                except urllib.error.HTTPError as error:
                    assert error.code == 403
                results["checks"].append("foreign-instance-shutdown-rejected")
                system = fetch("/api/system/info")
                assert system
                plugins = fetch("/api/plugins/")
                assert len(plugins) == 5, plugins
                fetch("/api/devices")
                for name in ("docker-manager", "software-installer", "ttyd-console", "webssh-plugin"):
                    # Startup executes compiled plugins and proves imports survived freezing.
                    # Only software_installer is non-invasive to start: no external service.
                    if name == "software-installer":
                        fetch("/api/plugins/" + name + "/start", "POST")
                        fetch("/api/plugins/" + name + "/stop", "POST")
                results["checks"] += ["system-info", "five-bundled-plugin-manifests", "device-storage",
                                     "compiled-software-installer-plugin-start-stop"]

                fetch("/rbox/shutdown", "POST", {"x-rbox-session": session})
                assert process.wait(timeout=10) == 0
                results["checks"].append("owned-instance-graceful-shutdown")
                assert (data / "config").is_dir()
                results["checks"].append("persistent-user-data-outside-payload")
            except Exception:
                print((data / "server-output.log").read_text(encoding="utf-8", errors="replace")[-12000:])
                raise
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
        results["result"] = "passed"
    output = ROOT / "artifacts/runtime-smoke.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
