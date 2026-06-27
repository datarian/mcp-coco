#!/usr/bin/env bash
set -euo pipefail

PGDATA_PATH="${PGDATA:-/var/lib/postgresql/data}"
POSTGRES_BIN="/usr/lib/postgresql/15/bin/postgres"
INITDB_BIN="/usr/lib/postgresql/15/bin/initdb"

if [[ ! -s "${PGDATA_PATH}/PG_VERSION" ]]; then
  install -d -o postgres -g postgres "${PGDATA_PATH}"
  su postgres -c "${INITDB_BIN} -D '${PGDATA_PATH}'"
fi

exec su postgres -c "${POSTGRES_BIN} -D '${PGDATA_PATH}' -c listen_addresses='*' -c port='5432'"