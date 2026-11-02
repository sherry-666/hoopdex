"""Two naive benchmarks for picking the winner of a game, next to the model (2016-17..2025-26 regular seasons).

  1. always pick the home team
  2. pick the team ranked higher in the standings going into the game (win% of games played so far this season;
     equal win% -- every game on opening night -- falls back to the home team)

The model row is the leave-one-season-out fit from scripts/backtest_predictor.py, on the same games.

Run: .venv/bin/python scripts/backtest_benchmarks.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).parent))
import backtest_predictor as bp   # noqa: E402
from ballstats import config   # noqa: E402


def standings_pick():
    """(season, game_id) -> home win% minus away win% before the game."""
    with psycopg.connect(config.DSN) as conn:
        g = pd.DataFrame(conn.execute(
            "SELECT season, game_id, game_date, team, team_score > opp_score FROM live.game"
            " WHERE completed AND season_type = 2 AND team_score IS NOT NULL").fetchall(),
            columns=["season", "gid", "date", "team", "won"])
    g = g.sort_values(["season", "team", "date", "gid"])
    g["gp"] = g.groupby(["season", "team"]).cumcount()
    g["w"] = g.groupby(["season", "team"]).won.cumsum() - g.won          # wins before this game
    g["pct"] = np.where(g.gp > 0, g.w / g.gp.clip(lower=1), 0.5)
    return g.set_index(["season", "gid", "team"]).pct


if __name__ == "__main__":
    pct = standings_pick()
    with psycopg.connect(config.DSN) as conn:
        games = pd.DataFrame(conn.execute(
            "SELECT season, game_id, team, opp, team_score - opp_score FROM live.game"
            " WHERE home AND completed AND season_type = 2 AND team_score IS NOT NULL").fetchall(),
            columns=["season", "gid", "h", "a", "m"])
    games["gap"] = [pct[(s, i, h)] - pct[(s, i, a)] for s, i, h, a in zip(games.season, games.gid, games.h, games.a)]
    games = games[games.season.map(lambda s: bp.FIRST <= int(s[:4]) <= bp.LAST)]
    win = games.m > 0
    games["rank_pick"] = games.gap >= 0                                    # ties -> home
    print(f"{len(games)} games (all)")
    print(f"  1 always home          {win.mean():.4f}")
    print(f"  2 higher in standings  {(games.rank_pick == win).mean():.4f}   (pick the home team on ties: {(games.gap == 0).mean():.1%} of games)")

    df = bp.build()
    cols = ["d_roster", "d_last", "b2b", "sform20"]
    print(f"\n{len(df)} games (model's frame, rows with all features)")
    ev = bp.evaluate(df, cols)
    print(f"  model ({'+'.join(cols)}) acc {ev['acc']:.4f}  logloss {ev['logloss']:.4f}")
