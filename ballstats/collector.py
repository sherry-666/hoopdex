"""Rate-limited, resumable fetcher for stats.nba.com via nba_api.

Every request is keyed by (endpoint, hash of params). A request that already
succeeded (and is fresh enough) is served from raw.raw_response, so an
interrupted run can simply be started again.
"""

import hashlib
import importlib
import json
import logging
import random
import time

import psycopg
from nba_api.stats.library.http import NBAStatsHTTP
from psycopg.types.json import Jsonb

from ballstats import config

log = logging.getLogger(__name__)


def params_hash(params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def is_empty_game_payload(body: dict) -> bool:
    """True for a V3 game response that came back with no players or events.

    stats.nba.com sometimes publishes a game's matchups hours after the
    final, answering with an empty shell until then. Caching that shell as
    'ok' would mean never fetching the real data.
    """
    if not body:   # a throttled request can come back as a bare {}
        return True
    if "game" in body and "actions" in body["game"]:
        return not body["game"]["actions"]
    for key, value in body.items():
        if key.startswith("boxScore") and isinstance(value, dict):
            return not (value.get("homeTeam") or {}).get("players")
    return False


def endpoint_class(name: str):
    module = importlib.import_module(f"nba_api.stats.endpoints.{name.lower()}")
    return getattr(module, name)


class Collector:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        self._last_request = 0.0
        self.stats = {"cached": 0, "fetched": 0, "failed": 0}

    def _throttle(self) -> None:
        wait = self._last_request + config.MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.3))
        self._last_request = time.monotonic()

    def _cached(self, endpoint: str, key: str, max_age_h: float | None) -> dict | None:
        row = self.conn.execute(
            "SELECT body FROM raw.raw_response"
            " WHERE endpoint = %s AND params_hash = %s AND status = 'ok'"
            "   AND (%s::float IS NULL OR fetched_at > now() - make_interval(secs => %s::float * 3600))",
            (endpoint, key, max_age_h, max_age_h),
        ).fetchone()
        return row[0] if row else None

    def _store(self, endpoint, key, params, status, body, error, attempts) -> None:
        self.conn.execute(
            """
            INSERT INTO raw.raw_response
                (endpoint, params_hash, params, status, body, error, attempts, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (endpoint, params_hash) DO UPDATE SET
                status = EXCLUDED.status,
                -- a failed refresh keeps the last good body
                body = COALESCE(EXCLUDED.body, raw.raw_response.body),
                error = EXCLUDED.error,
                attempts = EXCLUDED.attempts,
                fetched_at = EXCLUDED.fetched_at
            """,
            (endpoint, key, Jsonb(params), status,
             Jsonb(body) if body is not None else None, error, attempts),
        )

    def fetch(self, endpoint: str, params: dict, max_age_h: float | None = None,
              refresh: bool = False) -> dict | None:
        """max_age_h=None caches forever (finished games); a number re-fetches
        responses older than that (season aggregates that change nightly)."""
        key = params_hash(params)
        if not refresh:
            body = self._cached(endpoint, key, max_age_h)
            if body is not None:
                self.stats["cached"] += 1
                return body

        cls = endpoint_class(endpoint)
        error = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            self._throttle()
            try:
                # Build the request with nba_api but skip its parser: some
                # endpoints (e.g. BoxScoreMatchupsV3) break it, and we only
                # need the raw JSON.
                req = cls(**params, timeout=config.TIMEOUT_S, proxy=config.PROXY,
                          get_request=False)
                response = NBAStatsHTTP().send_api_request(
                    endpoint=req.endpoint, parameters=req.parameters,
                    proxy=config.PROXY, timeout=config.TIMEOUT_S,
                    raise_exception_on_error=True,
                )
                body = response.get_dict()
                if is_empty_game_payload(body):
                    # Not a transient error: retrying now won't help, the next run will.
                    self._store(endpoint, key, params, "error", None, "empty payload", attempt)
                    self.stats["failed"] += 1
                    return None
                self._store(endpoint, key, params, "ok", body, None, attempt)
                self.stats["fetched"] += 1
                return body
            except Exception as exc:  # timeouts, 429s and empty bodies all surface here
                error = f"{type(exc).__name__}: {exc}"[:2000]
                backoff = min(5 * 2 ** (attempt - 1), 120)
                log.warning("%s %s attempt %d failed: %s; retrying in %ds",
                            endpoint, params, attempt, error, backoff)
                if attempt < config.MAX_RETRIES:
                    time.sleep(backoff)

        self._store(endpoint, key, params, "error", None, error, config.MAX_RETRIES)
        self.stats["failed"] += 1
        return None


def result_rows(body: dict, set_name: str | None = None) -> list[dict]:
    """Rows of one result set as dicts, for both the resultSets and V3 shapes."""
    sets = body.get("resultSets") or body.get("resultSet")
    if isinstance(sets, dict):
        sets = [sets]
    for rs in sets or []:
        if set_name is None or rs.get("name") == set_name:
            return [dict(zip(rs["headers"], row)) for row in rs["rowSet"]]
    return []
