"""Polymarket's win probability of one NBA game: the moneyline market's price history.

A game's event is `nba-<away>-<home>-<ET game day>` (the same team codes as ours, lower case); its moneyline
market lists the away team first, and the price of a share is the market's win probability. Polymarket's public
read APIs need no key. Nothing is stored: the API asks on demand and keeps the answer for a while.
"""

import datetime as dt
import json
import logging
import time

import requests

log = logging.getLogger("ballstats.market")

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
FIDELITY = 10        # minutes between history points
TTL_OPEN, TTL_DONE, TTL_MISSING = 120, 6 * 3600, 600

_cache: dict[str, tuple[float, dict | None]] = {}


def _get(url: str, **params):
    res = requests.get(url, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; ballstats)"})
    res.raise_for_status()
    return res.json()


def fetch(away: str, home: str, day: dt.date) -> dict | None:
    """Home win probability now, before tipoff and over time; None when there is no market for the game."""
    slug = f"nba-{away.lower()}-{home.lower()}-{day.isoformat()}"
    events = _get(f"{GAMMA}/events", slug=slug)
    if not events:
        return None
    ev = events[0]
    mk = next((m for m in ev["markets"] if m.get("sportsMarketType") == "moneyline"), None)
    if mk is None:
        return None
    token = json.loads(mk["clobTokenIds"])[1]      # the home team's share
    hist = _get(f"{CLOB}/prices-history", market=token, interval="max", fidelity=FIDELITY).get("history", [])
    points = [[h["t"], round(h["p"], 4)] for h in hist]
    start = dt.datetime.fromisoformat((mk.get("gameStartTime") or ev["startTime"]).replace("Z", "+00:00").replace(" ", "T"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=dt.timezone.utc)
    ts = int(start.timestamp())
    before = [p for t, p in points if t <= ts]
    return {"slug": slug, "url": f"https://polymarket.com/event/{slug}", "start": ts, "closed": bool(ev.get("closed")),
            "volume": ev.get("volume"), "liquidity": ev.get("liquidity"),
            "pregame": before[-1] if before else None, "current": points[-1][1] if points else None, "history": points}


def game_market(away: str, home: str, day: dt.date) -> dict | None:
    key = f"{away}-{home}-{day}"
    hit = _cache.get(key)
    if hit and time.time() < hit[0]:
        return hit[1]
    try:
        data = fetch(away, home, day)
    except (requests.RequestException, KeyError, ValueError) as e:
        log.warning("polymarket %s: %s", key, e)
        if hit:      # stale beats nothing
            return hit[1]
        raise
    ttl = TTL_MISSING if data is None else TTL_DONE if data["closed"] else TTL_OPEN
    _cache[key] = (time.time() + ttl, data)
    return data
