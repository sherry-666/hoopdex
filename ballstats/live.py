"""Daily refresh of what changes between model runs: finished games and the injury report.

Both come from ESPN's public JSON, which answers cloud IPs (stats.nba.com does not), so this runs
as a Railway cron job. Players are matched to NBA ids by name. Ratings, roles and the other `feat`
tables are not touched; they still come from the local collection + `roles` / `ratings` pipeline.
"""

import datetime as dt
import logging
import re
import time
import unicodedata
from zoneinfo import ZoneInfo

import requests

from ballstats.cli import current_season

log = logging.getLogger("ballstats.live")

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
EASTERN = ZoneInfo("America/New_York")
# ESPN's team abbreviations that differ from stats.nba.com's.
TEAM_ABBR = {"UTAH": "UTA", "NO": "NOP", "NY": "NYK", "SA": "SAS", "GS": "GSW", "WSH": "WAS"}
BACKFILL_DAYS = 45
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (compatible; ballstats)"


def get_json(path: str, **params) -> dict:
    last: Exception | None = None
    for attempt in range(4):
        try:
            res = session.get(f"{BASE}/{path}", params=params, timeout=30)
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"ESPN {path} failed: {last}")


def norm(name: str) -> str:
    """'Jaren Jackson Jr.' -> 'jaren jackson'; accents, dots and suffixes dropped."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    words = re.sub(r"[^a-z0-9 ]", " ", s.replace("'", "")).split()
    return " ".join(w for w in words if w not in SUFFIXES)


def player_index(conn) -> dict[str, int]:
    """Normalized name -> NBA player id. Same-name players resolve to the one who played last."""
    rows = conn.execute(
        """
        SELECT player_id, name, coalesce(last_season, '') FROM core.player
        UNION ALL
        SELECT DISTINCT player_id, name, season FROM feat.player_stats WHERE season <> 'career'
        """).fetchall()
    best: dict[str, tuple[str, int]] = {}
    for pid, name, last in rows:
        key = norm(name)
        if key not in best or last > best[key][0]:
            best[key] = (last, pid)
    return {k: v[1] for k, v in best.items()}


def abbr(team: str) -> str:
    return TEAM_ABBR.get(team, team)


def parse_ts(s: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def update_injuries(conn, index: dict[str, int]) -> tuple[int, list[str]]:
    """Replace the injury report with ESPN's current one."""
    rows, unmatched = [], []
    for team in get_json("injuries")["injuries"]:
        for inj in team["injuries"]:
            ath, det = inj["athlete"], inj.get("details") or {}
            pid = index.get(norm(ath["displayName"]))
            if pid is None:
                unmatched.append(ath["displayName"])
            rows.append((int(inj["id"]), pid, ath["displayName"],
                         abbr(ath.get("team", {}).get("abbreviation", "")), inj["status"], det.get("type"),
                         det.get("detail"), det.get("side"), det.get("returnDate"),
                         inj.get("shortComment"), inj.get("longComment"), parse_ts(inj.get("date"))))
    if not rows:
        raise RuntimeError("ESPN returned an empty injury report; keeping the old one")
    with conn.transaction():
        conn.execute("DELETE FROM live.injury")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO live.injury (espn_id, player_id, name, team, status, body_part, detail, side, return_date,"
                " short_comment, long_comment, reported_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (espn_id) DO NOTHING", rows)
    return len(rows), unmatched


def split_made(s: str) -> tuple[int | None, int | None]:
    m = re.fullmatch(r"(\d+)-(\d+)", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def to_int(s: str | None) -> int | None:
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def game_rows(event: dict, index: dict[str, int], unmatched: set[str]) -> list[tuple]:
    summary = get_json("summary", event=event["id"])
    comp = summary["header"]["competitions"][0]
    date = parse_ts(comp["date"]).astimezone(EASTERN).date()
    teams = {c["team"]["id"]: c for c in comp["competitors"]}
    out = []
    for block in summary["boxscore"]["players"]:
        me = teams[block["team"]["id"]]
        opp = next(c for tid, c in teams.items() if tid != block["team"]["id"])
        stat = block["statistics"][0]
        keys = stat["keys"]
        for a in stat["athletes"]:
            name = a["athlete"]["displayName"]
            pid = index.get(norm(name))
            if pid is None:
                unmatched.add(name)
                continue
            v = dict(zip(keys, a.get("stats") or []))
            fgm, fga = split_made(v.get("fieldGoalsMade-fieldGoalsAttempted", ""))
            fg3m, fg3a = split_made(v.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted", ""))
            ftm, fta = split_made(v.get("freeThrowsMade-freeThrowsAttempted", ""))
            played = bool(v) and not a.get("didNotPlay")
            out.append((
                pid, event["id"], date, current_season(date), abbr(me["team"]["abbreviation"]),
                abbr(opp["team"]["abbreviation"]), me["homeAway"] == "home",
                to_int(me.get("score")), to_int(opp.get("score")), bool(a.get("starter")),
                None if played else (a.get("reason") or "DNP"),
                *(to_int(v.get(k)) if played else None for k in
                  ("minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "fouls")),
                *((fgm, fga, fg3m, fg3a, ftm, fta) if played else (None,) * 6),
                *(to_int(v.get(k)) if played else None for k in ("offensiveRebounds", "defensiveRebounds")),
                to_int((v.get("plusMinus") or "").lstrip("+")) if played else None,
            ))
    return out


GAME_COLS = ("player_id, game_id, game_date, season, team, opp, home, team_score, opp_score, started, dnp_reason,"
             " min, pts, reb, ast, stl, blk, tov, pf, fgm, fga, fg3m, fg3a, ftm, fta, oreb, dreb, plus_minus")


def update_games(conn, index: dict[str, int], days: int) -> tuple[int, list[str]]:
    """Box scores of games finished in the last `days` days (US Eastern) not stored yet."""
    today = dt.datetime.now(EASTERN).date()
    have = {r[0] for r in conn.execute("SELECT DISTINCT game_id FROM live.player_game")}
    unmatched: set[str] = set()
    n_games = 0
    for back in range(days, -1, -1):
        day = today - dt.timedelta(days=back)
        for event in get_json("scoreboard", dates=day.strftime("%Y%m%d"))["events"]:
            if event["status"]["type"]["name"] != "STATUS_FINAL" or event["id"] in have:
                continue
            rows = game_rows(event, index, unmatched)
            with conn.transaction(), conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO live.player_game ({GAME_COLS}) VALUES ({', '.join(['%s'] * 28)})"
                    " ON CONFLICT (player_id, game_id) DO NOTHING", rows)
            n_games += 1
            log.info("%s %s: %d player lines", day, event["shortName"], len(rows))
    return n_games, sorted(unmatched)


def update(conn, days: int = 3) -> dict:
    index = player_index(conn)
    if not conn.execute("SELECT 1 FROM live.player_game LIMIT 1").fetchone():
        days = max(days, BACKFILL_DAYS)   # first run: fill the season so far
    n_games, missed_g = update_games(conn, index, days)
    n_inj, missed_i = update_injuries(conn, index)
    unmatched = sorted(set(missed_g) | set(missed_i))
    conn.execute("INSERT INTO live.update_log (games, injuries, unmatched) VALUES (%s, %s, %s)",
                 (n_games, n_inj, unmatched))
    if unmatched:
        log.warning("%d names without an NBA id: %s", len(unmatched), ", ".join(unmatched[:20]))
    return {"games": n_games, "injuries": n_inj, "unmatched": len(unmatched)}
