# Desktop, Synology and R-File Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task in this session.

**Goal:** Build and open R-Link locally, deliver real tray/autostart behavior, reuse R-File network/file services and produce usable NAS installation artifacts.

**Architecture:** Extend the existing Tauri tray with the official autostart plugin. A FastAPI adapter talks to existing R-File services and keeps secrets server-side. NAS packaging reuses the existing backend/web Docker architecture with explicit persistent volumes and authenticated ingress.

**Tech Stack:** Tauri 2, Rust, React/TypeScript, FastAPI/httpx, SQLite, Docker, DSM package lifecycle scripts.

### Task 1: Desktop startup and tray

Files: `apps/r-link-web/src-tauri/{Cargo.toml,Cargo.lock,src/lib.rs,src/desktop_tray.rs}`, `apps/r-link-web/src/components/modals/{DesktopSettings.tsx,DesktopSettings.test.tsx}`.

1. Write failing tests for the real autostart setting, busy/error handling, startup hiding only with a usable tray and ordinary launch showing the window. Run focused Vitest and Rust tests and observe failure due to absent behavior.
2. Add the desktop-only official autostart plugin, with LaunchAgent on macOS and `--autostart` args. Keep single-instance first. Native custom commands query/set autostart; no broad new frontend plugin permissions.
3. Extend settings and tray menu with consistent actual OS state and errors. Auto launch hides only after tray creation succeeds; ordinary relaunch restores.
4. Run focused tests, typecheck and existing window tests. Commit the reviewed feature.

### Task 2: Reuse R-File services

Files: create `R-Link-Server/core/rfile.py`, `R-Link-Server/api/rfile.py`, `R-Link-Server/test_rfile.py`; modify `R-Link-Server/main.py`; create `apps/r-link-web/src/api/rfile.ts`, `apps/r-link-web/src/components/pages/RFileView.tsx` and behavioral tests; modify existing navigation and lazy view registration.

1. Add failing contract tests for automatic loopback service discovery, existing RFILE environment conventions, authentication on R-Link routes, R-File health identity validation, no token disclosure, credential-safe redirects, bridge registration/heartbeat and cleanup.
2. Implement a bounded adapter over actual watch/bridge routes, not a new network service. Default bases are `http://127.0.0.1:18080` and `http://127.0.0.1:18100`; explicit R-Link overrides take precedence over RFILE conventions. A dedicated controller registers with canInitiate=true/canAccept=false, persists its identity atomically with restricted permissions, heartbeats and observes bridge devices. Never revoke/update another device or export secrets.
3. Test and implement configured-root watch browsing/upload/download. Require an explicit configured credential and root for filesystem access; construct paths from validated relative components and retain R-File permissions. Bound bytes/time/concurrency and propagate sanitized status rather than raw upstream exception/headers. Abort-safe streaming cleanup.
4. Add a visible R-File page showing service and network states, R-File devices and root-restricted file operations. Preserve the original shared-files page. Meaningful tests cover offline/error, no false connected state, transfers and root restrictions.
5. Run focused backend/frontend tests and full API regression. Commit, spec review then quality review.

### Task 3: NAS installation versions

Files: `deploy/nas/`, `scripts/build_nas_package.py`, `R-Link-Server/test_nas_package.py`, `docs/desktop-nas-rfile-20261003.md`, optional `.github/workflows/desktop-packages.yml` for native desktop architecture builds.

1. Specify/tests first for reproducible installation archive, no secrets/runtime data in archives, required source/dependency lockfiles, persistent volumes, auth and upgrade/uninstall preservation.
2. Produce a self-contained Docker source installation archive supporting native amd64/arm64 builds. Include token generation, `.env` template, LAN web binding, R-File endpoint mapping, startup/restart and backup/upgrade instructions.
3. Build amd64 Docker images in existing Tencent Docker tooling without affecting production service; verify ports, auth, health, storage persistence and clean temporary containers.
4. Package a DSM 7.1 apollolake Docker-backed SPK if available tooling allows offline images and appropriate package dependency/lifecycle behavior. Label model/arch/version explicitly and validate archive/scripts without claiming NAS installation when unreachable.
5. Produce hashes, manifest and readable installation instructions. Spec and quality review.

### Task 4: Local install, launch and completion

1. Integrate only reviewed commits after full checks and original-source preservation verification. Confirm current main has not diverged before fast-forwarding.
2. Build NSIS from the integrated source. Install to a stable per-user location, open the application, enable autostart as requested and inspect the actual startup registration (path plus `--autostart`).
3. Native Windows UI check: close retains same PID, repeated launch restores one instance, startup launch remains accessible through tray, explicit exit works; leave the final user application open.
4. Verify real R-File bridge using isolated test identity/real server; remove only owned test identity/files. Deliver actual artifact links, hashes, passing evidence and untested hardware/platform limits.

Commands: `npx vitest run --pool threads --maxWorkers 1 --no-file-parallelism`, `node --test src-tauri/src/project-window-chrome.test.cjs`, `cargo test --manifest-path src-tauri/Cargo.toml --locked --lib --features custom-protocol`, `npm run build`, `L:\project\R-Link\.venv\Scripts\python.exe -m pytest R-Link-Server -q`, `python scripts/verify_web_migration.py`, `npm run tauri:build -- --bundles nsis`. Tests must produce zero failures; artifact/platform claims require a completed build or a stated limitation.
