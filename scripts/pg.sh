#!/usr/bin/env bash
# Project-local Postgres on localhost:5433 (trust auth, data in .pgdata/).
# Usage: scripts/pg.sh start|stop|status|psql
set -euo pipefail
cd "$(dirname "$0")/.."
PG_BIN="${PG_BIN:-/Library/PostgreSQL/17/bin}"
DATA=.pgdata

case "${1:-status}" in
  start)
    if [ ! -d "$DATA" ]; then
      "$PG_BIN/initdb" -D "$DATA" -U ballstats --auth=trust -E UTF8 --locale=en_US.UTF-8
      printf "port = 5433\nlisten_addresses = 'localhost'\nunix_socket_directories = ''\n" >> "$DATA/postgresql.conf"
      "$PG_BIN/pg_ctl" -D "$DATA" -l "$DATA/server.log" -w start
      "$PG_BIN/createdb" -h localhost -p 5433 -U ballstats ballstats
    else
      "$PG_BIN/pg_ctl" -D "$DATA" -l "$DATA/server.log" -w start
    fi ;;
  stop)   "$PG_BIN/pg_ctl" -D "$DATA" stop ;;
  status) "$PG_BIN/pg_ctl" -D "$DATA" status ;;
  psql)   shift; exec "$PG_BIN/psql" -h localhost -p 5433 -U ballstats ballstats "$@" ;;
  *) echo "usage: $0 start|stop|status|psql" >&2; exit 1 ;;
esac
