# R-Link NAS Docker installation

Target: **Synology DS918+ / DSM 7.1.1 / apollolake / x86_64 (linux/amd64)**.
Release: `0.1.0-nas.20261003`. This is a Docker installation archive, **not a Package Center SPK**.
The offline variant includes tested amd64 server and web images. The source variant builds natively on
amd64 or arm64 Linux with Docker; arm64 wheel availability was checked, but no arm64 image/runtime or
Linux/macOS desktop installer was built here. Inspect `PACKAGE-MANIFEST.json` for the exact source
commit, files, image IDs and platforms. Base image tags are resolved at build time, so source archive
bytes are reproducible from a commit; rebuilding Docker images later is not promised to be identical.

## Before installing

Install DSM 7.1's official **Docker** package and enable it to start at boot. Use an administrator SSH
session for Docker commands (`sudo -i` if needed); membership in the Docker group is root-equivalent,
so do not grant that group or mount the Docker socket into R-Link. Ensure `docker compose version` or
`docker-compose version` works. The script supports both. Required Docker Engine: 20.10 or newer
(`host-gateway` support). Port 8080 must be free; change `R_LINK_WEB_PORT` in `.env` if needed.

Create a private installation directory in a persistent shared folder, for example
`/volume1/docker/r-link/releases/20261003`. Upload the archive and its `.sha256` sidecar there. Verify
the digest on the NAS before extraction (or verify it on the uploading computer if `sha256sum` is absent):

```sh
cd /volume1/docker/r-link/releases/20261003
sha256sum -c r-link-nas-0.1.0-nas.20261003-DS918plus-DSM7.1.1-apollolake-amd64-offline.tar.gz.sha256
tar -xzf r-link-nas-0.1.0-nas.20261003-DS918plus-DSM7.1.1-apollolake-amd64-offline.tar.gz
cd r-link-nas/deploy/nas
./init.sh
./rlink.sh load
```

`init.sh` generates 32 random bytes as a 64-character key in `.env` with mode 0600. Re-running it
retains the original key and refuses a symlink or invalid existing key. Never distribute `.env`.
Privately edit it: append the actual NAS browser origin to `R_LINK_CORS_ORIGINS`, retaining both
`tauri://localhost` and `http://tauri.localhost` for desktop connections. For example:
`R_LINK_CORS_ORIGINS=http://localhost:8080,tauri://localhost,http://tauri.localhost,http://192.168.1.8:8080`.
Append the trusted HTTPS origin too when configuring a reverse proxy; this setting replaces the
backend's default list, so keep the desktop origins. Set the R-File endpoints as described below. Then:

```sh
./rlink.sh start
./rlink.sh status
./rlink.sh logs
curl -f http://127.0.0.1:8080/health
```

Open `http://NAS-IP:8080` on the LAN and enter the generated service key in R-Link. An API request
without that key receives HTTP 401; the health endpoint and static frontend are public. Backend 8210
is internal to the Docker network and has **no host port**. Only the web port binds the LAN.
For remote desktop connections, expose this web port through DSM's HTTPS reverse proxy with a
trusted certificate and configure the desktop's server address as `https://your-domain`. Avoid sending
keys over untrusted HTTP networks. For a self-signed HTTPS R-File endpoint, provide its explicit public
CA to the backend; never disable TLS certificate verification. The offline package contains no private
certificate, token, host identity, runtime database or existing user files.

## R-File network and file access

Defaults map the NAS host through `host.docker.internal:host-gateway`:

```dotenv
R_LINK_RFILE_URL=http://host.docker.internal:18080
R_LINK_RFILE_BRIDGE_URL=http://host.docker.internal:18100
R_LINK_RFILE_INTERVAL=30
```

The existing RFileNAS watch must listen on an interface reachable by containers (normally `0.0.0.0`),
and the DSM firewall must allow the Docker subnet. The bridge can instead be an existing trusted
HTTPS URL, including an application base prefix. If bridge 18100 listens only on host loopback, the
container cannot use it through host-gateway: explicitly configure a reachable HTTPS bridge instead.
This adapter automatically checks health, registers its own controller and sends heartbeats; it never
creates fictional SSH/VPN routes. Controller identity persists in the data volume with private 0700/0600
permissions. Existing R-File package files and their permissions remain unchanged.

File operations stay disabled until the R-File owner explicitly provides both a scope and credential:

```dotenv
R_LINK_RFILE_ROOT=/volume1/lcx
R_LINK_RFILE_SESSION_TOKEN=THE_EXPLICITLY_GRANTED_SESSION_TOKEN
```

That root is the **actual absolute path on the R-File server**, not a symlink or an R-Link container
mount. The preferred session token uses `x-rfile-session-token`; an explicitly granted long-lived
credential can use `R_LINK_RFILE_TOKEN` instead. Do not read private 0600 RFileNAS token files or
relax their permissions. Network discovery works independently of filesystem credentials. Files use
relative paths, reject links and overwrites, and are bounded to 64 MiB each.

For an explicitly trusted R-File CA, add a read-only mount under server `volumes` in `compose.yaml`:

```yaml
      - /volume1/docker/r-link/trust/rfile-ca.crt:/opt/rlink/trust/rfile-ca.crt:ro
```

Set `R_LINK_RFILE_CA_CERT=/opt/rlink/trust/rfile-ca.crt` in `.env`. Only mount a **public CA certificate**.
Do not ship your private keys or disable HTTPS checks. To use optional FRP/Caddy tools, explicitly
mount a directory containing trusted compatible binaries as `/opt/rlink/bin:ro`, and add the required
`R_LINK_FRPC_BINARY`/`R_LINK_CADDY_BINARY` variables to server environment. Those binaries and
their service credentials are not included and are not assumed available.

## Startup, backup, upgrade and uninstall

Both containers use `restart: unless-stopped`: they recover when Docker/NAS starts unless deliberately
stopped. On a real NAS, verify this after a DSM reboot; physical DSM installation/reboot was unavailable
for this release. `./rlink.sh stop`, `./rlink.sh start` and `./rlink.sh restart` control the installation.

Project `r-link-nas` and named volumes `rlink-nas-data`, `rlink-nas-config`, `rlink-nas-plugins`,
`rlink-nas-logs` stay fixed across archive directory changes. They contain shared files, SQLite device
metadata, service state, private R-File controller identity, plugin/config/log data. Do not change
`R_LINK_VOLUME_PREFIX` for upgrades. Do not delete these volumes or use Docker's volume-pruning UI.
Docker's own named volume storage must reside on persistent NAS storage with sufficient space.

Create a consistent **backup** with services stopped. The backup directory must be private, outside
the extracted release and unique for this backup. It includes credentials and controller identity:

```sh
./rlink.sh stop
mkdir -p /volume1/docker/r-link/backups
./rlink.sh backup /volume1/docker/r-link/backups/20261003
./rlink.sh start
```

To **upgrade**, stop and back up first; extract the new archive into a new directory, copy the old
private `.env` (preserving permissions), and load the new images. Set its `R_LINK_IMAGE_TAG` to the
new manifest's version, preserve the same volume prefix, CORS/R-File settings and optional mounts:

```sh
cp -p /volume1/docker/r-link/releases/OLD/r-link-nas/deploy/nas/.env ./deploy/nas/.env
cd deploy/nas
# Edit R_LINK_IMAGE_TAG to the version in this release's PACKAGE-MANIFEST.json.
./rlink.sh load
./rlink.sh upgrade
./rlink.sh status
```

To **uninstall** containers: `./rlink.sh uninstall`. This performs Compose `down` without volume
deletion and retains `.env` and all four named volumes. Reinstall with that same `.env` and volume
prefix to recover data. Uninstalling DSM's Docker package or manually deleting its storage is outside
this script and can remove volumes: back up first.

To restore a trusted backup, stop containers; preserve current data separately, and restore each tar
into its corresponding **empty** volume. The archive is private and should only come from your own
backup; extraction can overwrite files. Example for the data volume (repeat with `/app/config`,
`/app/plugins`, `/app/logs` and matching archive/volume):

```sh
# With Docker available, import/load the server image first.
docker volume create rlink-nas-data
docker run --rm -i --user 10001 --entrypoint python -v rlink-nas-data:/restore \
  rlink-nas-server:0.1.0-nas.20261003 -c \
  'import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode="r|gz"); t.extractall("/restore",filter="data")' \
  < /volume1/docker/r-link/backups/20261003/data.tar.gz
# Restore rlink.env to deploy/nas/.env with mode 0600, then ./rlink.sh start.
```

A newly created empty volume mounted at `/restore` is root-owned. Prepare it with one explicit root
container that only changes ownership of the new empty restore directory (`chown 10001:10001 /restore`)
before the above extraction. Never recursively change ownership of an R-File share or existing volume.

## Native source build and release verification

On a native amd64 or arm64 Linux host, extract the source archive, run `./init.sh`, then `./rlink.sh build`
and `./rlink.sh start`. The server uses Python 3.12 Alpine and a fully pinned production dependency lock
with binary wheels; frontend uses `npm ci` and its committed package lock. No QEMU/cross-build tooling
is installed by these scripts. For a Docker registry proxy, pass temporary build arguments; never persist
proxy URLs or tokens in image environment. A source build requires access to the base-image registry,
PyPI and npm. Offline installation requires only the two included app images and existing DSM Docker.

Release generation from a clean committed revision:

```sh
python scripts/build_nas_package.py --ref HEAD --output /private/releases
docker save -o /private/rlink-images.tar \
  rlink-nas-server:0.1.0-nas.20261003 rlink-nas-web:0.1.0-nas.20261003
python scripts/build_nas_package.py --ref HEAD --output /private/releases \
  --image-archive /private/rlink-images.tar
```

The builder reads whitelisted committed Git blobs, normalizes shell scripts to executable LF files,
fixes tar/gzip timestamps and ownership, validates both offline image platforms/non-root server/config
secrets, and emits SHA256 sidecars plus a readable manifest. It does not copy working-tree changes.
Final amd64 verification covers authenticated ingress, health, UI, uploads/downloads, non-root server,
controller/database/file persistence across restart and container removal/recreation. These Linux Docker
checks are not proof of physical DSM installation, hardware performance or reboot behavior.

## Why this release withholds an SPK

DSM 7.1 supports the [Docker worker](https://help.synology.com/developer-guide/resource_acquisition/docker.html),
but its own `shares` are removed at uninstall. The retained
[data-share worker](https://help.synology.com/developer-guide/resource_acquisition/data_share.html) acquires
at `FROM_ENABLE_TO_POSTUNINST`, while Docker acquisition is `FROM_POSTINST_TO_PREUNINST`.
[Resource timing](https://help.synology.com/developer-guide/resource_acquisition/timing.html) puts Docker's
`WHEN_POSTINST` before `postinst`; a generated key/config or retained-share symlink cannot simply be
assumed available for container creation. A preexisting share/target symlink alternative has not been
validated on DSM. An offline worker could build packaged rootfs contexts without loading images in a
privileged script; this does not resolve the unverified storage/permission/lifecycle ordering.
The [package privilege rules](https://help.synology.com/developer-guide/privilege/privilege_config.html)
also favor a package user. This release avoids root/Docker-socket permissions inside an SPK and does
not claim a safe Package Center lifecycle without a reachable NAS. ContainerManager's Docker-project
worker requires DSM 7.2.1 and cannot be used on this target. The tested offline Docker archive provides
explicit administrator installation with durable volumes instead.
