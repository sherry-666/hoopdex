# HoopDex

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
.venv/bin/python -m ballstats ratings                    # -> feat.player_rating, feat.player_career_rating
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
languages) are generated. Set `BALLSTATS_SITE_URL` (e.g. `https://hoopdex.app`) so canonical URLs use the
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

Load the data (only `feat` by default; the site needs nothing else). Collection and model fitting stay on
this machine, since stats.nba.com blocks cloud IPs; re-run this after `ballstats roles`:

```bash
REMOTE_DATABASE_URL="$(railway variables --service Postgres --json | jq -r .DATABASE_PUBLIC_URL)" scripts/push_db.sh
```

Comic portraits: drop `web/public/portraits/<player_id>.webp` (5:6 aspect, about 840x1008). Players without one show a placeholder.
Superpowers come from `ballstats/powers.py`: a player's most extreme style stats (z >= 1 among 500+ minute players),
graded S / A / B, each quoting the stat behind it.
