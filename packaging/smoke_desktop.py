"""Native window + owned backend launch check; terminates only its test process."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import psutil

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "artifacts/payload/rlink-tauri.exe"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
USER32 = ctypes.windll.user32
ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
USER32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]


def visible_windows(pid):
    result = []
    @ENUMPROC
    def callback(window, _):
        process_id = wintypes.DWORD()
        USER32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        if process_id.value == pid and USER32.IsWindowVisible(window):
            title = ctypes.create_unicode_buffer(256)
            USER32.GetWindowTextW(window, title, len(title))
            rect = wintypes.RECT()
            USER32.GetWindowRect(window, ctypes.byref(rect))
            if title.value and rect.right - rect.left > 500 and rect.bottom - rect.top > 400:
                result.append({"title": title.value, "width": rect.right - rect.left, "height": rect.bottom - rect.top})
        return True
    USER32.EnumWindows(callback, 0)
    return result


def main():
    results = {"productId": "r-link", "desktop": str(EXE), "checks": []}
    with tempfile.TemporaryDirectory(prefix="r-link-gui-smoke-") as directory:
        environment = os.environ.copy()
        environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        environment["WEBVIEW2_USER_DATA_FOLDER"] = str(Path(directory) / "webview-profile")
        with (Path(directory) / "output.log").open("wb") as output:
            desktop = subprocess.Popen([str(EXE)], cwd=directory, env=environment,
                stdout=output, stderr=subprocess.STDOUT, creationflags=0x08000000)
            backend = None
            try:
                deadline = time.monotonic() + 55
                while time.monotonic() < deadline:
                    if desktop.poll() is not None:
                        raise RuntimeError(f"Desktop exited ({desktop.returncode}) before window/backend acceptance")
                    process = psutil.Process(desktop.pid)
                    children = process.children()
                    backend = next((child for child in children if child.name() == "r-link-server.exe"), None)
                    windows = visible_windows(desktop.pid)
                    ports = [connection.laddr.port for connection in psutil.net_connections(kind="tcp")
                             if connection.status == "LISTEN" and backend and connection.pid == backend.pid]
                    if windows and ports:
                        with OPENER.open(f"http://127.0.0.1:{ports[0]}/rbox/health", timeout=5) as response:
                            health = json.load(response)
                        if health["service"] == "r-link" and health["status"] == "healthy":
                            results["window"] = windows[0]
                            results["backendPort"] = ports[0]
                            break
                    time.sleep(0.25)
                else:
                    raise RuntimeError("Native window or owned backend did not become ready")
                results["checks"] += ["native-visible-window", "owned-packaged-backend", "backend-instance-health",
                                     "empty-working-directory", "no-python-on-PATH"]
                desktop.terminate()
                desktop.wait(timeout=10)
                backend.wait(timeout=15)
                results["checks"].append("backend-exit-after-unexpected-parent-termination")
                results["result"] = "passed"
            except Exception:
                print((Path(directory) / "output.log").read_text(encoding="utf-8", errors="replace")[-12000:])
                raise
            finally:
                if desktop.poll() is None:
                    desktop.kill()
                    desktop.wait(timeout=10)
                try:
                    if backend and backend.is_running():
                        # Only this test's directly owned backend may be cleaned up.
                        backend.kill()
                        backend.wait(timeout=10)
                except psutil.NoSuchProcess:
                    pass
    (ROOT / "artifacts/native-window-smoke.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    report = ROOT / "artifacts/native-runtime-smoke.json"
    environment = os.environ.copy()
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    subprocess.run([str(EXE), "--rbox-runtime-check", str(report)], cwd=ROOT / "artifacts",
                   env=environment, check=True, timeout=60, creationflags=0x08000000)
    native_runtime = json.loads(report.read_text(encoding="utf-8"))
    assert native_runtime["result"] == "passed" and native_runtime["backendStopped"]
    print(json.dumps(native_runtime, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
