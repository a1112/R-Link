"""Reproducible Windows preview payload builder (run with the locked Python 3.12 venv)."""
import argparse
import json
import importlib.metadata
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "R-Link-Server"
OUT = ROOT / "artifacts"
PAYLOAD = OUT / "payload"
ID = "r-link"


def run(*args, cwd=ROOT):
    subprocess.run(list(args), cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-only", action="store_true")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Windows runtime builds are locked to Python 3.12")
    OUT.mkdir(exist_ok=True)
    PAYLOAD.mkdir(exist_ok=True)
    freezer = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
               "--name", ID + "-server", "--distpath", str(OUT / "frozen"),
               "--workpath", str(OUT / "freeze-work"), "--specpath", str(OUT),
               "--paths", str(SERVER), "--collect-submodules", "uvicorn",
               "--collect-submodules", "core", "--collect-submodules", "api",
               "--collect-submodules", "websockets"]
    freezer += ["--hidden-import", "requests"]
    resources = OUT / "compiled-builtin"
    for source_dir in (SERVER / "builtin").iterdir():
        if not source_dir.is_dir():
            continue
        dest = resources / source_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        for source in source_dir.iterdir():
            if source.suffix in (".yaml", ".json"):
                shutil.copy2(source, dest / source.name)
            elif source.suffix == ".py":
                py_compile.compile(str(source), cfile=str(dest / source.with_suffix(".pyc").name),
                                   dfile=f"builtin/{source_dir.name}/{source.name}", doraise=True)
    freezer += ["--add-data", str(resources) + ";builtin"]

    run(*freezer, str(SERVER / "desktop_runtime.py"))
    shutil.copytree(OUT / "frozen" / (ID + "-server"), PAYLOAD / "runtime", dirs_exist_ok=True)
    # The nginx controller is a separate binary plugin; rebuild its launcher as well.
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--name", "nginx-plugin", "--distpath", str(OUT / "plugin-frozen"),
        "--workpath", str(OUT / "plugin-work"), "--specpath", str(OUT),
        str(SERVER / "builtin/nginx-plugin/nginx-plugin.py"))
    nginx = PAYLOAD / "runtime/_internal/builtin/nginx-plugin"
    nginx.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT / "plugin-frozen/nginx-plugin.exe", nginx / "nginx-plugin.exe")

    if not args.runtime_only:
        run("cmd.exe", "/c", "npm.cmd", "ci", cwd=ROOT / "apps/r-link-web")
        run("cmd.exe", "/c", "npm.cmd", "run", "build", cwd=ROOT / "apps/r-link-web")

        run("cargo", "+1.94.1", "build", "--release", "--locked", "-j4", "--manifest-path",
            str(ROOT / "apps/r-link-web/src-tauri/Cargo.toml"), "--bin", "rlink-tauri", "--features", "custom-protocol")
    desktop = ROOT / "apps/r-link-web/src-tauri/target/release/rlink-tauri.exe"
    if desktop.is_file():
        shutil.copy2(desktop, PAYLOAD / desktop.name)
    licenses = PAYLOAD / "licenses"
    licenses.mkdir(exist_ok=True)
    # Preserve redistributable Python and wheel license notices in the payload.
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "PYTHON-LICENSE.txt")
    for distribution in importlib.metadata.distributions():
        for item in distribution.files or ():
            if item.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                source = distribution.locate_file(item)
                if source.is_file():
                    destination = licenses / "python" / distribution.metadata["Name"] / item.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    for pattern in ("LICENSE*", "COPYING*", "NOTICE*"):
        for source in ROOT.glob(pattern):
            if source.is_file():
                shutil.copy2(source, licenses / source.name)
    version = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (PAYLOAD / "build-info.json").write_text(json.dumps({
        "productId": ID, "sourceCommit": version, "python": sys.version,
        "platform": "windows-x64", "runtime": "PyInstaller 6.20.0"
    }, indent=2) + "\n", encoding="utf-8")
    print(PAYLOAD)


if __name__ == "__main__":
    main()
