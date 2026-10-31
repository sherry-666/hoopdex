# Hoopedia

NBA player analytics and prediction platform. Design doc: https://claude.ai/artifact/XxBkiYmw93SMzduJ2LCQwo

## Setup

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e .
scripts/pg.sh start          # project-local Postgres on localhost:5433, data in .pgdata/
.venv/bin/python -m ballstats init-db
```

## Collecting data

```bash
.venv/bin/python -m ballstats collect                         # current season, all groups
.venv/bin/python -m ballstats collect --season 2025-26 --groups season,games
.venv/bin/python -m ballstats status --season 2026-27
```

- Requests go out at most once per second; failures back off and retry, then are recorded as `error`.
- Every response lands verbatim in `raw.raw_response`, keyed by endpoint + params hash. Re-running skips
  what is already there: finished games are cached for good, season aggregates are refetched after 20 h.
- stats.nba.com blocks most cloud IPs. Run from a home network, or set `BALLSTATS_PROXY`.

Settings (env): `BALLSTATS_DSN`, `BALLSTATS_MIN_INTERVAL`, `BALLSTATS_MAX_RETRIES`, `BALLSTATS_TIMEOUT`, `BALLSTATS_PROXY`.

## Roles model

```bash
.venv/bin/python -m ballstats roles --season 2025-26   # families + archetype mixes, map, axes, stat views
```

Writes `feat.player_role`, `feat.role_type`, `feat.player_view`, `feat.role_axis` and `feat.player_stats`.

Other seasons are projected onto that model, so roles mean the same thing every season (the explorer
views stay with the reference season):

```bash
.venv/bin/python -m ballstats roles --season 2024-25 --reference 2025-26
```

## Ratings

```bash
.venv/bin/python -m ballstats collect --groups history   # league box + advanced totals, 1996-97 to now (~60 requests)
.venv/bin/python -m ballstats ratings                    # -> feat.player_rating, feat.player_career_rating, feat.player_season_box (the Rankings stat leaders)
```

OVR (40-99) per player season from three z-scores against that season's 500+ minute players: PIE (40%),
scoring volume and efficiency (40%) and minutes-shrunk on-court net rating (20%), pulled toward replacement
by sample size and scaled as 77 + 6.5 z. Peak = best three qualifying seasons in a row; career = 0.7 peak +
0.3 minutes-weighted average. Details in `ballstats/ratings.py`; the player page explains it too.

Offense and defense ratings use the same scale and pipeline, computed separately (OVR is not their average):
offense = scoring 45%, playmaking (AST% − 0.5 × TOV ratio) 25%, OREB% 10%, on-court offense 20%; defense =
steals/36 20%, blocks/36 15%, DREB% 15%, on-court defense 50%. On-court numbers are measured against his own
team plus 30% of the team's edge on the league, so a strong team doesn't lift everyone.

While a season is in progress (nobody has 70 games yet), the site defaults to it and its model outputs are
transition values (`ballstats/blend.py`): ratings, archetype mixes, superpowers and team styles / ratings are
`w x this season + (1 - w) x last season`, with w = minutes / (minutes + 600) for players and
games / (games + 20) for teams. Box-score stats are never blended. `roles` re-applies the blend after every
rebuild; run `ratings` and `teams` after it.

Team styles (进攻体系, offensive systems) come from how a team runs its offense, not from its players' archetypes: Synergy play-type mix,
passes / drives / elbow, post and paint touches per 100, seconds and dribbles per touch, catch-and-shoot vs
pull-up share, shot zones, assisted share and pace (`ballstats/team_features.py`), standardized within each
season and clustered (k-means, 5 styles) on every team season since 2015-16. Collect the inputs once with
`python -m ballstats collect --groups teams` (~23 requests per season). Against shuffled data this separates
four times better than clustering the rotation's archetype mix did, and 59% of teams keep their style the
next season (chance: 25%); it is still a continuum, so a style means "closest to".

Team ratings (`python -m ballstats teams`, centred on 80) are half the rotation's minutes-weighted player
ratings and half the team's actual net / offensive / defensive rating per 100 possessions, z-scored per season.

To rebuild every season with tracking data on one model, plus the career view (each player's seasons
averaged by minutes, stored as season `career`), with the cluster-view axes fitted once and shared:

```bash
.venv/bin/python -m ballstats roles --all --season 2025-26
```

## Careers

```bash
.venv/bin/python -m ballstats collect --groups careers   # PlayerCareerStats for every player (~700 requests)
.venv/bin/python -m ballstats parse                      # -> core.player, core.player_season, core.player_career
```

`core.player_season` has one row per player, season, season type and team (a traded player also gets a
`TOT` row); `core.player_career` has career totals for the regular season and playoffs.
Family and archetype names live in `ballstats/role_names.json`, tied to the model version.

## Web app

FastAPI (`ballstats/api.py`) serves `/api/*` from the feat tables; the React app lives in `web/`.

```bash
.venv/bin/uvicorn ballstats.api:app --port 8000      # API
npm --prefix web install && npm --prefix web run dev  # http://localhost:5173, proxies /api to :8000
```

For a single server, `npm --prefix web run build` and the API also serves `web/dist` at http://localhost:8000.

### SEO

The app renders in the browser, so the API fills `index.html` per route (`ballstats/seo.py`): title,
description, canonical URL, hreflang, Open Graph / Twitter tags, JSON-LD and a plain-HTML summary inside
`#root` that React replaces on mount. Unknown routes, players and seasons return 404. Chinese is the
default; `?lang=en` is the English version of any page. `/robots.txt` and `/sitemap.xml` (every player, both
languages) are generated. Set `BALLSTATS_SITE_URL` (e.g. `https://hoopedia.app`) so canonical URLs use the
public domain. Only the built app on :8000 does this; the Vite dev server doesn't.

## Deploy (Railway)

The `Dockerfile` builds the frontend and serves it plus the API from one FastAPI process; `railway.json`
points Railway at it with a health check on `/api/seasons`. The app reads `DATABASE_URL` (or `BALLSTATS_DSN`).

```bash
railway login                                    # once, opens the browser
railway init -n ballstats                        # new project
railway add --database postgres                  # managed Postgres
railway add --service web
railway variables --service web --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}'
railway up --service web                         # build and deploy this folder
railway domain --service web                     # public URL
```

Load the data (only `feat` by default; the site needs nothing else). This needs a TCP Proxy on the Postgres
service (dashboard: Postgres → Settings → Networking, port 5432); remove it again once the data is loaded. Collection and model fitting stay on
this machine, since stats.nba.com blocks cloud IPs; re-run this after `ballstats roles`:

```bash
REMOTE_DATABASE_URL="$(railway variables --service Postgres --json | jq -r '"postgresql://postgres:\(.POSTGRES_PASSWORD)@\(.RAILWAY_TCP_PROXY_DOMAIN):\(.RAILWAY_TCP_PROXY_PORT)/railway"')" scripts/push_db.sh
```

### Daily update (cron)

`python -m ballstats live-update [--days 3]` pulls finished games' box scores and the current injury report
from ESPN's public feeds (which, unlike stats.nba.com, answer cloud IPs) into the `live` schema
(`live.player_game`, `live.injury`, `live.standing`; `ballstats/live.py`). Players are matched to NBA ids by name; names it
cannot match (mostly rookies not in the data yet) are logged and skipped. The player page shows the injury
as a banner (current season only) and the last 10 games. It also keeps the conference standings per season (1996-97 on; past seasons are fetched once, the current one every run),
which feed the Rankings tab together with the player ratings in `feat`. It does not touch `feat`: ratings, roles and
team styles still come from the local pipeline. `push_db.sh` only replaces `raw` / `feat`, so `live` survives it.

On Railway it is a second service from the same repo and image, run on a schedule (`railway.cron.json`, 11:00 and 21:00 UTC
daily: after the last games end in the US, and again before the evening tip-offs so the injury report is fresh):

1. Dashboard → New → GitHub repo / empty service named `espn-cron`; deploy the same source (`railway up --service espn-cron`).
2. Service → Settings → Config-as-code → file path `/railway.cron.json`.
3. Service → Variables: `DATABASE_URL=${{Postgres.DATABASE_URL}}`.
4. The first run, with an empty `live.player_game`, looks back 45 days to fill the season so far.

### Hourly schedule update (third cron)

`python -m ballstats schedule-update` is the light part of `live-update`: schedule and scores, the injury report and the
standings (about 7 s, no box scores, no team ratings). Service `schedule-cron`, same repo, `0 * * * *`, start command
`python -m ballstats schedule-update` (`railway.schedule.json` has the same settings; Railway no longer reads
config-as-code for a service made from the CLI, so they are set on the service itself), `DATABASE_URL=${{Postgres.DATABASE_URL}}`.
It keeps the game predictions on `/predict` current: tonight's scores and injury changes show up within the hour.

### Daily prediction snapshot (fourth cron)

`python -m ballstats snapshot` stores the model's prediction for each unfinished game of today (US Eastern) and the next 3 days in
`live.prediction_snapshot`: margin, win probability, every component, the raw inputs (rotation ratings healthy / on the day /
effective, recent form, back-to-back, constants) and the injury report for both teams, plus the full `/api/predict` payload.
Later, join `game_id` to `live.game` for the final score and fit the coefficients (`INJURY_AMP`, `C_ROSTER`, ...).
Service `snapshot-cron`, `0 17 * * *` (noon US Eastern in winter, 1 pm in summer; `railway.snapshot.json` has the settings,
which are set on the service itself), start command `python -m ballstats snapshot`, `DATABASE_URL=${{Postgres.DATABASE_URL}}`.
Re-running on the same day replaces that day's snapshot. `/api/predict` reads the latest snapshot of a game back (finished
or not) instead of recomputing, and falls back to a live computation when the game has none.

### Nightly nba stats update (second cron)

`python -m ballstats daily-update` is the Railway-side version of the local routine: it collects the current
season from stats.nba.com (season, games, players, history, teams; cached requests are skipped), then runs
`roles --reference <previous season>`, `ratings` and `teams`. If collection does not fully succeed (for example
stats.nba.com refuses the host) it exits non-zero before touching `feat`. It refuses to run when `raw` for the
reference season is missing, since every past season would be refetched.

Setup: load `raw` once (`REMOTE_DATABASE_URL=<DATABASE_PUBLIC_URL> scripts/push_db.sh raw`), add a second cron
service `nba-cron` with config file `/railway.nba.json` (hourly, `0 * * * *`; the cache lets it resume where the last run stopped), `DATABASE_URL=${{Postgres.DATABASE_URL}}`,
and `BALLSTATS_PROXY` if stats.nba.com blocks Railway's IPs.

Comic portraits: drop `web/public/portraits/<player_id>.webp` (5:6 aspect, about 840x1008). Players without one show a placeholder.
Superpowers come from `ballstats/powers.py`: a player's most extreme style stats (z >= 1 among 500+ minute players),
graded S / A / B, each quoting the stat behind it.
