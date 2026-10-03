# R-Link Windows managed preview

This private release branch adds the self-contained desktop payload consumed by R-Box.
The original checkout is not used during launch. Private server modules are frozen
inside the PyInstaller archive; R-Link built-in plugins are shipped as compiled
bytecode and manifests.

## Reproduce

Use Windows 11 x64, Node 24, Rust 1.94.1 and Python 3.12. A Microsoft C++ toolchain
and WebView2 Runtime must be present.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r packaging/requirements-windows.lock.txt
.venv/Scripts/python.exe packaging/build_windows.py
.venv/Scripts/python.exe packaging/smoke_runtime.py
artifacts/payload/rlink-tauri.exe --rbox-runtime-check artifacts/native-runtime-smoke.json
```

The package root is `artifacts/payload`; it contains `rlink-tauri.exe`,
`runtime/r-link-server.exe`, its adjacent `_internal` runtime tree, licenses and
`build-info.json`. Keep this tree intact. Do not distribute `.venv`, Python source,
the source repository, PyInstaller build directories or Node modules.

The desktop starts its own loopback server and requires a product-and-instance
health response before showing the application. Normal desktop exit requests
graceful shutdown, then kills only its owned child if shutdown exceeds six seconds.
A parent-process watcher also stops the backend after an unexpected desktop exit.
When port 8210 is already owned, the desktop chooses an unused loopback port and communicates its endpoint to the client through native IPC. It does not reuse or stop the other service.

User files live under `%LOCALAPPDATA%/R-Link`, independently of R-Box's version
directory. Uninstalling managed application files therefore preserves user data.
The `--rbox-runtime-check` command exercises native packaged backend start, health
and shutdown without a WebView. The Python smoke additionally checks API resources
with Python removed from PATH and an empty working directory.

## Preview acceptance boundaries

The base server, SQLite device storage, five built-in plugin manifests and compiled software-installer plugin load/start/stop are included. FRP, NetBird, nginx, ttyd and Docker are optional operator-managed services; their external binaries are not supplied in this preview. The API reports missing executables explicitly. Remote SSH, plugin downloads, VPN pairing and external service controls still require separate product acceptance.
macOS and Linux packaging and native launch have not been validated by this branch.
The runtime checks do not constitute clean-OS validation or full product acceptance.
