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

# Unattended runs: give up after this many seconds of fetching (0 = no limit) or after this many
# requests in a row that failed every retry (0 = never); the next run resumes from the cache.
RUN_BUDGET_S = float(os.environ.get("BALLSTATS_RUN_BUDGET_S", "0"))
MAX_CONSECUTIVE_FAILURES = int(os.environ.get("BALLSTATS_MAX_CONSECUTIVE_FAILURES", "0"))

# Optional, e.g. http://user:pass@host:port. Cloud IPs are usually blocked.
PROXY = os.environ.get("BALLSTATS_PROXY") or None

# Built frontend served by the API. Defaults to web/dist next to the package source.
WEB_DIST = Path(os.environ.get("BALLSTATS_WEB_DIST") or Path(__file__).resolve().parent.parent / "web" / "dist")

# Public origin for canonical URLs and the sitemap, e.g. https://hoopedia.app. Without it
# the request's own host is used.
SITE_URL = (os.environ.get("BALLSTATS_SITE_URL") or "").rstrip("/") or None
