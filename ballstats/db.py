from importlib import resources

import psycopg

from ballstats import config


def connect() -> psycopg.Connection:
    return psycopg.connect(config.DSN, autocommit=True)


def init_schema(conn: psycopg.Connection) -> list[str]:
    applied = []
    sql_dir = resources.files("ballstats") / "sql"
    for path in sorted(p for p in sql_dir.iterdir() if p.name.endswith(".sql")):
        conn.execute(path.read_text())
        applied.append(path.name)
    return applied
