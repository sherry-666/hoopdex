#!/usr/bin/env bash
# Copy the local database into a remote Postgres, replacing those schemas there.
#   REMOTE_DATABASE_URL='postgresql://...' scripts/push_db.sh          # feat only: what the web app reads
#   REMOTE_DATABASE_URL='postgresql://...' scripts/push_db.sh raw feat # also the raw API responses (~90 MB)
#   REMOTE_DATABASE_URL='postgresql://...' scripts/push_db.sh core     # honors and career totals the web app reads (hall of fame)
# On Railway, use the Postgres service's DATABASE_PUBLIC_URL (reachable from outside).
set -euo pipefail
cd "$(dirname "$0")/.."
PG_BIN="${PG_BIN:-/Library/PostgreSQL/17/bin}"
: "${REMOTE_DATABASE_URL:?set REMOTE_DATABASE_URL to the remote connection string}"
SCHEMAS=("${@:-feat}")
[ $# -eq 0 ] && SCHEMAS=(feat)

drops=""; flags=()
for s in "${SCHEMAS[@]}"; do
  case "$s" in raw|feat|core) ;; *) echo "unknown schema: $s (use raw, feat and/or core)" >&2; exit 1 ;; esac
  drops+="DROP SCHEMA IF EXISTS $s CASCADE; "
  flags+=(-n "$s")
done

"$PG_BIN/psql" "$REMOTE_DATABASE_URL" -v ON_ERROR_STOP=1 -q -c "$drops"
# Strip a PG17-only SET so older servers accept the dump.
"$PG_BIN/pg_dump" -h localhost -p 5433 -U ballstats --no-owner --no-privileges "${flags[@]}" ballstats \
  | grep -v '^SET transaction_timeout' \
  | "$PG_BIN/psql" "$REMOTE_DATABASE_URL" -v ON_ERROR_STOP=1 -q

for s in "${SCHEMAS[@]}"; do
  "$PG_BIN/psql" "$REMOTE_DATABASE_URL" -At -c \
    "SELECT '$s: ' || string_agg(relname || ' ' || n_live_tup, ', ') FROM pg_stat_user_tables WHERE schemaname = '$s';"
done
