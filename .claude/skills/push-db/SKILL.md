---
name: push-db
description: Push the local ballstats Postgres data (feat schema, optionally raw) to the Railway production database. Use when the user asks to push/sync/deploy the database or data to Railway or production.
---

# Push local DB to Railway Postgres

The web app on Railway (hoopdex.up.railway.app) reads the `feat` schema. Code deploys itself on `git push` to main, but data does not: it has to be copied from the local Postgres (port 5433, `.pgdata`) with `scripts/push_db.sh`.

## Rules

- **Only when the user asks.** Pushing replaces production data. Commit/push code first if the user wants that; the DB step comes after.
- **The user must open Railway Postgres public access first** (Railway dashboard → Postgres service → Settings → Networking → public networking / TCP proxy). Ask them to do so and wait for confirmation. After the push, tell them they can close it again.
- Never print the connection string or write it to a file.

## Steps

1. Make sure local feat is what should ship (e.g. `python -m ballstats ...` jobs finished, local Postgres running on 5433).
2. Get the public URL (needs the logged-in Railway CLI; the `RAILWAY_TOKEN` env var may be stale, so unset it):
   ```bash
   env -u RAILWAY_TOKEN railway variables --service Postgres --kv | grep '^DATABASE_PUBLIC_URL='
   ```
   If the service name differs, run `env -u RAILWAY_TOKEN railway status` to find it. If the CLI is not linked/logged in, ask the user to paste `DATABASE_PUBLIC_URL` from the dashboard instead.
3. Run the push (feat only is the default; add `raw` only if the user wants the raw API responses, ~90 MB):
   ```bash
   REMOTE_DATABASE_URL='<DATABASE_PUBLIC_URL>' scripts/push_db.sh          # feat
   REMOTE_DATABASE_URL='<DATABASE_PUBLIC_URL>' scripts/push_db.sh raw feat # feat + raw
   ```
   Needs network access outside the sandbox. The script drops the schema(s) on the remote, then pipes `pg_dump` from local into `psql`, and finally prints row counts per table.
4. Verify: compare the printed row counts with local, then check the site, e.g.
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://hoopdex.up.railway.app/api/players
   ```
   expecting 200 on the main endpoints (`/api/players`, `/api/roles/matchups`, `/api/roles/synergy/offense`).
5. Tell the user to close public access in Railway.

## Gotchas

- **Brief outage:** the schema is dropped before reload, so the site returns errors for the duration of the push (about a minute). Don't leave it half done: if the output ends with `server terminated abnormally` or a psql error, re-run the same command until it completes, then re-verify.
- `pg_dump` is PG17 (`PG_BIN` defaults to `/Library/PostgreSQL/17/bin`); the script strips the PG17-only `SET transaction_timeout` so older servers accept the dump.
- New tables need their migration applied locally first (`ballstats/sql/*.sql`); the push copies whatever is in local `feat`, so prod gets them automatically.
- UI-only commits don't need a DB push.
