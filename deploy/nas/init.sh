#!/bin/sh
set -eu
umask 077
directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$directory"
if [ -L .env ]; then
    echo '.env must be a private regular file, not a symlink' >&2
    exit 1
fi
if [ -e .env ]; then
    if ! grep -Eq '^R_LINK_API_TOKEN=[A-Za-z0-9_-]{32,}$' .env; then
        echo 'Existing .env retained; set a random API token before starting' >&2
        exit 1
    fi
    echo 'Existing .env retained; service key unchanged'
    exit 0
fi
token=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
[ "${#token}" -eq 64 ] || { echo 'Random key generation failed' >&2; exit 1; }
# noclobber prevents concurrent installation from overwriting another key.
(set -C; sed "s/^R_LINK_API_TOKEN=$/R_LINK_API_TOKEN=$token/" .env.example > .env)
echo 'Created private .env (0600). Read its key locally for the R-Link sign-in screen.'
