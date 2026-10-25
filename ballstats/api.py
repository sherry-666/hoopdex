"""HTTP API for the web app. Read-only over the feat layer.

Run: .venv/bin/uvicorn ballstats.api:app --port 8000
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ballstats import config, powers, roles

app = FastAPI(title="ballstats")
WEB_DIST: Path = config.WEB_DIST
HEADLINE = ["pts_36", "reb_36", "ast_36", "ts_pct", "usg_pct", "fg3a_36", "stl_36", "blk_36"]
SIDES = ("offense", "defense")

# Reused connections: opening one per query is slow against a remote database.
pool = ConnectionPool(config.DSN, min_size=1, max_size=8, kwargs={"row_factory": dict_row}, open=False)


@app.on_event("startup")
def _open_pool() -> None:
    pool.open()


@app.on_event("shutdown")
def _close_pool() -> None:
    pool.close()


def q(sql: str, params: tuple | dict = ()) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


def check_side(side: str) -> None:
    if side not in SIDES:
        raise HTTPException(404, f"unknown side {side!r}")


# A season counts as complete enough to rank players once this many have 500+ minutes.
MIN_QUALIFIED = 100


@app.get("/api/seasons")
def seasons() -> list[dict]:
    """Every season with player data, newest first. in_progress = too few players with
    500+ minutes to compare against; has_views = the role explorer has data for it."""
    rows = q(
        """
        SELECT s.season, count(*) AS players, count(*) FILTER (WHERE s.minutes >= %s) AS qualified,
               EXISTS (SELECT 1 FROM feat.player_view v WHERE v.season = s.season) AS has_views
        FROM feat.player_stats s WHERE s.season <> 'career' GROUP BY s.season ORDER BY s.season DESC
        """, (roles.MIN_MINUTES,))
    for r in rows:
        r["in_progress"] = r["qualified"] < MIN_QUALIFIED
    return rows


@app.get("/api/roles/{season}/{side}")
def role_view(season: str, side: str) -> dict:
    """Everything the role explorer draws for one side: families, archetypes with
    their profiles, the cluster-view axes, and every shown player."""
    check_side(side)
    types = q("SELECT level, type_id, name, n_fit, profile FROM feat.role_type"
              " WHERE season = %s AND side = %s ORDER BY level, type_id", (season, side))
    if not types:
        raise HTTPException(404, f"no role model for {season}")
    axes = q("SELECT method, axis, name, high, low FROM feat.role_axis"
             " WHERE season = %s AND side = %s ORDER BY axis", (season, side))
    players = q(
        """
        SELECT r.player_id, s.name, s.team, s.minutes, r.in_fit, r.family_id, r.family_name,
               r.top_archetype_id, r.top_weight, r.style_label, r.weights,
               v.x, v.y, v.f1, v.f2, v.f3, v.l1, v.l2, v.l3
        FROM feat.player_role r
        JOIN feat.player_view v USING (season, player_id, side)
        JOIN feat.player_stats s USING (season, player_id)
        WHERE r.season = %s AND r.side = %s
        """, (season, side))
    return {
        "families": [t for t in types if t["level"] == "family"],
        "archetypes": [t for t in types if t["level"] == "archetype"],
        "axes": axes,
        "players": players,
    }


@app.get("/api/stats/{season}")
def stats(season: str) -> list[dict]:
    return q("SELECT player_id, minutes, stats FROM feat.player_stats WHERE season = %s", (season,))


@app.get("/api/players/{season}")
def player_list(season: str) -> list[dict]:
    return q(
        """
        SELECT s.player_id, s.name, s.team, s.gp, s.minutes,
               (s.minutes >= %(min)s) AS in_fit,
               (s.stats ->> 'pts_36')::float AS pts_36, (s.stats ->> 'ts_pct')::float AS ts_pct,
               (s.stats ->> 'usg_pct')::float AS usg_pct,
               o.family_name AS off_family, o.style_label AS off_style, o.top_archetype_id AS off_top,
               d.family_name AS def_family, d.style_label AS def_style, d.top_archetype_id AS def_top,
               rt.ovr
        FROM feat.player_stats s
        LEFT JOIN feat.player_rating rt ON rt.season = s.season AND rt.player_id = s.player_id
        LEFT JOIN feat.player_role o ON o.season = s.season AND o.player_id = s.player_id AND o.side = 'offense'
        LEFT JOIN feat.player_role d ON d.season = s.season AND d.player_id = s.player_id AND d.side = 'defense'
        WHERE s.season = %(season)s
        ORDER BY s.minutes DESC
        """, {"season": season, "min": roles.MIN_MINUTES})


def compare_season(season: str) -> str:
    """The season players are ranked against: this one, or while it is still early,
    the newest season before it with enough players at 500+ minutes."""
    rows = q(
        """
        SELECT season FROM feat.player_stats WHERE season <= %s AND season <> 'career' GROUP BY season
        HAVING count(*) FILTER (WHERE minutes >= %s) >= %s ORDER BY season DESC LIMIT 1
        """, (season, roles.MIN_MINUTES, MIN_QUALIFIED))
    return rows[0]["season"] if rows else season


@lru_cache(maxsize=8)
def league_table(season: str) -> pd.DataFrame:
    """Stat values of players with 500+ minutes, one row per player."""
    rows = q("SELECT player_id, stats FROM feat.player_stats WHERE season = %s AND minutes >= %s",
             (season, roles.MIN_MINUTES))
    return pd.DataFrame({r["player_id"]: r["stats"] for r in rows}).T.astype(float)


def archetype_names(season: str) -> dict[tuple[str, int], str]:
    rows = q("SELECT side, type_id, name FROM feat.role_type WHERE season = %s AND level = 'archetype'", (season,))
    return {(r["side"], r["type_id"]): r["name"] for r in rows}


@app.get("/api/players/{season}/{player_id}")
def player(season: str, player_id: int) -> dict:
    rows = q("SELECT player_id, name, team, gp, minutes, stats FROM feat.player_stats"
             " WHERE season = %s AND player_id = %s", (season, player_id))
    if not rows:
        raise HTTPException(404, "player not found")
    me = rows[0]
    versus = compare_season(season)
    league = league_table(versus)
    mean, sd = league.mean(), league.std()
    values = me["stats"]
    z = {k: float((v - mean[k]) / sd[k]) for k, v in values.items()
         if v is not None and k in mean and sd[k] > 0}
    pct = {k: float((league[k].dropna() <= values[k]).mean()) for k in HEADLINE
           if values.get(k) is not None and k in league}

    names = archetype_names(season)
    role_rows = q("SELECT * FROM feat.player_role WHERE season = %s AND player_id = %s", (season, player_id))
    sides = {}
    for r in role_rows:
        mix = sorted(({"id": int(a), "name": names.get((r["side"], int(a))), "weight": w}
                      for a, w in r["weights"].items()), key=lambda m: -m["weight"])
        peers = q(
            """
            SELECT r.player_id, s.name, s.team, r.style_label, r.weights
            FROM feat.player_role r JOIN feat.player_stats s USING (season, player_id)
            WHERE r.season = %s AND r.side = %s AND r.family_id = %s AND r.in_fit AND r.player_id <> %s
            """, (season, r["side"], r["family_id"], player_id))
        for p in peers:
            dist = sum(abs(p["weights"].get(k, 0) - w) for k, w in r["weights"].items()) / 2
            p["similarity"] = round(1 - dist, 3)
            del p["weights"]
        sides[r["side"]] = {
            "family": r["family_name"], "style": r["style_label"], "top_weight": r["top_weight"],
            "in_fit": r["in_fit"], "mix": mix,
            "similar": sorted(peers, key=lambda p: -p["similarity"])[:5],
        }
    return {
        "player_id": me["player_id"], "name": me["name"], "team": me["team"], "gp": me["gp"],
        "minutes": me["minutes"], "in_fit": me["minutes"] >= roles.MIN_MINUTES,
        "stats": values, "percentiles": pct, "compare_season": versus, "roles": sides,
        "powers": powers.powers_for(z, values),
        "rating": rating_for(season, player_id),
        "career_rating": career_rating_for(player_id),
    }


def rating_for(season: str, player_id: int) -> dict | None:
    rows = q("SELECT ovr, z, qualified, baseline_season, minutes, gp, detail, model_version FROM feat.player_rating"
             " WHERE season = %s AND player_id = %s", (season, player_id))
    return rows[0] if rows else None


def career_rating_for(player_id: int) -> dict | None:
    rows = q("SELECT peak, peak_from, peak_to, avg_ovr, career, seasons, qualified_seasons FROM feat.player_career_rating"
             " WHERE player_id = %s", (player_id,))
    return rows[0] if rows else None


@app.get("/api/teams/{season}")
def team_view(season: str) -> dict:
    """Team-building styles and every team's rotation profile for one season."""
    styles = q("SELECT style_id, name, description, centroid FROM feat.team_style ORDER BY style_id")
    teams = q("SELECT team, style_id, defense_tag, off_mix, def_mix, off_z, avg_ovr, rotation_minutes, core"
              " FROM feat.team_profile WHERE season = %s ORDER BY avg_ovr DESC NULLS LAST", (season,))
    if not teams:
        raise HTTPException(404, f"no team profiles for {season}")
    arch = q("SELECT DISTINCT side, type_id, name FROM feat.role_type WHERE level = 'archetype' ORDER BY side, type_id")
    return {"styles": styles, "teams": teams,
            "archetypes": {side: [r["name"] for r in arch if r["side"] == side] for side in SIDES}}


@app.get("/api/player/{player_id}/seasons")
def player_seasons(player_id: int) -> list[str]:
    """Seasons this player has style and role data for, newest first."""
    return [r["season"] for r in q("SELECT season FROM feat.player_stats WHERE player_id = %s AND season <> 'career'"
                                   " ORDER BY season DESC", (player_id,))]


@app.get("/api/player/{player_id}/career")
def player_career(player_id: int) -> dict:
    """Box-score totals for every season of his career plus career totals, regular season
    and playoffs. A traded player's season shows his combined line, with the teams listed."""
    players = q("SELECT name, first_season, last_season FROM core.player WHERE player_id = %s", (player_id,))
    rows = q("SELECT * FROM core.player_season WHERE player_id = %s ORDER BY season, season_type, team", (player_id,))
    ovr = {r["season"]: r for r in q("SELECT season, ovr, qualified FROM feat.player_rating WHERE player_id = %s", (player_id,))}
    out: dict = {"player": players[0] if players else None, "regular": [], "playoffs": [], "career": {},
                 "rating": career_rating_for(player_id)}
    for stype in ("regular", "playoffs"):
        by_season: dict[str, list[dict]] = {}
        for r in rows:
            if r["season_type"] == stype:
                by_season.setdefault(r["season"], []).append(r)
        for season, stints in by_season.items():
            line = next((r for r in stints if r["team"] == "TOT"), stints[0])
            teams = [r["team"] for r in stints if r["team"] != "TOT"]
            out[stype].append({**{k: v for k, v in line.items() if k not in ("player_id", "season_type", "team_id")},
                               "team": "/".join(teams) or line["team"],
                               "ovr": ovr[season]["ovr"] if stype == "regular" and season in ovr else None,
                               "ovr_qualified": ovr[season]["qualified"] if stype == "regular" and season in ovr else None})
    for r in q("SELECT * FROM core.player_career WHERE player_id = %s", (player_id,)):
        out["career"][r["season_type"]] = {k: v for k, v in r.items() if k not in ("player_id", "season_type")}
    return out


# The built frontend, when present (npm run build in web/). Unknown paths fall back to
# index.html so client-side routes work on reload.
if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "unknown API route")
        target = WEB_DIST / path
        return FileResponse(target if path and target.is_file() else WEB_DIST / "index.html")
