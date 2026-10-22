# Desktop, NAS and R-File delivery — 2026-10-03

Desktop behavior includes tray residency, explicit quit, close-to-tray and saved autostart settings.
R-File integration automatically checks/registers/heartbeats network services; file access requires an
explicit credential and absolute scope. NAS delivery is described in [deploy/nas/README.md](../deploy/nas/README.md).

NAS target is DS918+ / DSM 7.1.1 / apollolake x86_64. Deliverables are a reproducible committed-source
archive (native amd64/arm64 build inputs) and an offline amd64 Docker image installation archive, with
manifest/hash sidecars. Only amd64 images were built/run. ARM64 binary wheel availability was checked
without an ARM64 build/runtime claim. Linux/macOS native desktop installers require native CI/build hosts.

The NAS script generates its private service key at install, never overwrites an existing key, keeps API
8210 private, binds authenticated web ingress to LAN8080, and uses stable named volumes. Startup uses
Docker restart policy. Backups include metadata/shared files/service state/controller identity; upgrade
and container uninstall retain .env and all volumes. Physical NAS installation/reboot is unverified because
192.168.1.8:18080 was unreachable and no DSM credentials were supplied.

No Package Center SPK is emitted. The retained data-share acquisition is later than Docker creation,
Docker-worker shares alone are removed on uninstall, and a safe preexisting-share/config lifecycle could
not be validated on DSM. See the official lifecycle references and precise fallback reasoning in the
installation guide. No NAS token files were read and no R-File permissions or repository files changed.

Existing deployments remain unchanged during NAS builds/QA. Release manifests record the exact source
commit and image IDs; a reviewed final commit can regenerate source/offline wrapper archives from the
same actual images after source provenance is checked.
