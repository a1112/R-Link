#!/bin/sh
set -eu
umask 077
directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$directory"
compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose --project-directory "$directory" -p "${R_LINK_PROJECT:-r-link-nas}" -f "$directory/compose.yaml" "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose --project-directory "$directory" -p "${R_LINK_PROJECT:-r-link-nas}" -f "$directory/compose.yaml" "$@"
    else
        echo 'Install Docker with docker compose or docker-compose first' >&2
        exit 1
    fi
}
command=${1:-status}
case "$command" in
    init) exec "$directory/init.sh" ;;
    load) docker load -i "$directory/../../images.tar" ;;
    build) "$directory/init.sh"; compose build ;;
    start) "$directory/init.sh"; compose up -d --no-build ;;
    stop) compose stop ;;
    restart) compose restart ;;
    status) compose ps ;;
    logs) compose logs --tail=100 ;;
    upgrade) "$directory/init.sh"; compose up -d --no-build --force-recreate ;;
    uninstall) compose down; echo 'Containers removed. All named volumes and .env retained.' ;;
    backup)
        destination=${2:?Specify an absolute backup directory outside this release}
        case "$destination" in /*) ;; *) echo 'Backup directory must be absolute' >&2; exit 1 ;; esac
        release=$(CDPATH= cd -- "$directory/../.." && pwd -P)
        parent=$(CDPATH= cd -- "$(dirname -- "$destination")" && pwd -P)
        destination="${parent%/}/$(basename -- "$destination")"
        case "$destination" in "$release"|"$release"/*)
            echo 'Backup must be outside the extracted release' >&2; exit 1 ;;
        esac
        # Compare directory identity too: mount aliases can name the same release.
        probe=$parent
        while :; do
            if [ "$probe" -ef "$release" ]; then
                echo 'Backup must be outside the extracted release' >&2; exit 1
            fi
            [ "$probe" = / ] && break
            probe=$(dirname -- "$probe")
        done
        if [ -e "$destination" ] || [ -L "$destination" ]; then
            echo 'Backup destination must be new; existing directories and symlinks are retained' >&2
            exit 1
        fi
        # Refuse reuse: an interrupted/new backup must never overwrite the only copy.
        mkdir "$destination"
        chmod 700 "$destination"
        cp -p "$directory/.env" "$destination/rlink.env"
        compose stop
        # Failures leave services stopped; the caller explicitly starts after verification.
        for role in data config plugins logs; do
            compose run -T --rm --no-deps --entrypoint python server -c 'import sys,tarfile; p={"data":"/data","config":"/app/config","plugins":"/app/plugins","logs":"/app/logs"}[sys.argv[1]]; t=tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz"); t.add(p,arcname="."); t.close()' "$role" > "$destination/$role.tar.gz"
        done
        echo 'Backup created; protect this directory because it includes keys and controller identity.'
        ;;
    *) echo 'Usage: rlink.sh init|load|build|start|stop|restart|status|logs|upgrade|uninstall|backup /absolute/path' >&2; exit 2 ;;
esac
