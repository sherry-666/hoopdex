import os
from pathlib import Path

# BALLSTATS_DSN wins; DATABASE_URL is what Railway (and most hosts) inject for an
# attached Postgres; otherwise the project-local cluster from scripts/pg.sh.
DSN = (
    os.environ.get("BALLSTATS_DSN")
    or os.environ.get("DATABASE_URL")
    or "host=localhost port=5433 dbname=ballstats user=ballstats"
)

# stats.nba.com throttles aggressive clients; stay at or under 1 request/second.
MIN_INTERVAL_S = float(os.environ.get("BALLSTATS_MIN_INTERVAL", "1.0"))
MAX_RETRIES = int(os.environ.get("BALLSTATS_MAX_RETRIES", "5"))
TIMEOUT_S = int(os.environ.get("BALLSTATS_TIMEOUT", "30"))

# Optional, e.g. http://user:pass@host:port. Cloud IPs are usually blocked.
PROXY = os.environ.get("BALLSTATS_PROXY") or None

# Built frontend served by the API. Defaults to web/dist next to the package source.
WEB_DIST = Path(os.environ.get("BALLSTATS_WEB_DIST") or Path(__file__).resolve().parent.parent / "web" / "dist")
