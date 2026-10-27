"""Style matchups: which offensive systems do well against which defensive systems?

Unit: a team's score in one regular-season game. Every team-season gets its own offense level and its
own defense level (fixed effects), so everything about team quality (player talent, coaching, pace) is
removed, along with the home edge (per season). What is left to explain is the interaction: does an offensive system
score more or less than the two teams' levels predict when it meets a given defensive system?
Main effects of a style are absorbed by those levels, so only the interaction (a doubly centred
offence x defence table, 12 degrees of freedom) is reported.

Offensive system = feat.team_system.style_id (how a team plays); defensive system =
feat.team_profile.defense_tag (the kind of defender its rotation leans on). Only complete seasons are fitted.
Cell noise is large (hundreds of games per cell, ~12 points of game-to-game sd), so each cell comes with
a bootstrap standard error, an empirical-Bayes shrunk effect, and the whole table with a permutation test
against shuffled defensive labels.
"""

import numpy as np
import pandas as pd
import psycopg
from scipy import sparse
from scipy.sparse.linalg import lsqr

MIN_GAMES = 60          # a season is complete once every team has played this many (shortened 2019-20, 2020-21 count)
BOOTSTRAPS = 200
PERMUTATIONS = 200
SEED = 0
RIDGE = 1.0             # only makes the redundant cell dummies unique; the table is centred afterwards


def load_games(conn: psycopg.Connection) -> pd.DataFrame:
    """One row per team-game of the complete regular seasons that have both kinds of system."""
    rows = conn.execute(
        """
        SELECT g.season, g.game_id, g.team, g.opp, g.home, g.team_score, o.style_id, d.defense_tag
        FROM live.game g
        JOIN feat.team_system o ON o.season = g.season AND o.team = g.team
        JOIN feat.team_profile d ON d.season = g.season AND d.team = g.opp
        WHERE g.season_type = 2 AND g.completed AND g.team_score IS NOT NULL
          AND g.season IN (SELECT season FROM live.game WHERE season_type = 2 AND completed
                           GROUP BY season, team HAVING count(*) >= %s
                           INTERSECT SELECT season FROM feat.team_profile)
        """, (MIN_GAMES,)).fetchall()
    g = pd.DataFrame(rows, columns=["season", "game_id", "team", "opp", "home", "pts", "off_style", "def_style"])
    g["a"], g["b"] = g.season + "|" + g.team, g.season + "|" + g.opp
    return g


def _design(g: pd.DataFrame, cells: list[str]) -> tuple[sparse.csr_matrix, int]:
    a = pd.get_dummies(g.a).astype(float).to_numpy()
    b = pd.get_dummies(g.b).astype(float).to_numpy()
    cell = pd.get_dummies(g.off_style.astype(str) + "|" + g.def_style).reindex(columns=cells, fill_value=0).astype(float).to_numpy()
    # The home edge is its own number per season: 2019-20 restarted in a bubble, 2020-21 had few crowds.
    home = pd.get_dummies(g.season).astype(float).mul(g.home.astype(float), axis=0).to_numpy()
    k = a.shape[1] + b.shape[1] + home.shape[1]
    return sparse.csr_matrix(np.hstack([a, b, home, cell])), k


def fit_table(g: pd.DataFrame, offs: list[int], defs: list[str]) -> pd.DataFrame:
    """Interaction table (offence style x defence style), points per game."""
    cells = [f"{o}|{d}" for o in offs for d in defs]
    X, k = _design(g, cells)
    pen = sparse.hstack([sparse.csr_matrix((len(cells), k)), sparse.identity(len(cells)) * np.sqrt(RIDGE)])
    coef = lsqr(sparse.vstack([X, pen]), np.concatenate([g.pts.to_numpy(float), np.zeros(len(cells))]),
                atol=1e-10, btol=1e-10, iter_lim=20000)[0][k:]
    m = pd.DataFrame(coef.reshape(len(offs), len(defs)), index=offs, columns=defs)
    return m.sub(m.mean(axis=1), axis=0).sub(m.mean(axis=0), axis=1) + m.to_numpy().mean()


def compute(conn: psycopg.Connection) -> dict:
    g = load_games(conn)
    if g.empty:
        return {"games": 0}
    offs, defs = sorted(g.off_style.unique()), sorted(g.def_style.unique())
    table = fit_table(g, offs, defs)
    rng = np.random.default_rng(SEED)

    # Bootstrap over games (a game contributes both teams' scores, so resample game ids).
    by_game = g.groupby("game_id").indices
    ids = np.array(list(by_game))
    boots = np.array([fit_table(g.iloc[np.concatenate([by_game[i] for i in rng.choice(ids, len(ids))])], offs, defs).to_numpy()
                      for _ in range(BOOTSTRAPS)])
    se = pd.DataFrame(boots.std(axis=0), index=offs, columns=defs)

    # Permutation test: shuffle the defensive labels among the team-seasons of each season.
    spread = lambda t: float((t.to_numpy() ** 2).sum())
    team_def = g.drop_duplicates("b").set_index("b")[["season", "def_style"]]
    null = []
    for _ in range(PERMUTATIONS):
        shuffled = team_def.groupby("season")["def_style"].transform(lambda s: rng.permutation(s.to_numpy()))
        null.append(spread(fit_table(g.assign(def_style=g.b.map(shuffled)), offs, defs)))
    p_value = float((1 + sum(n >= spread(table) for n in null)) / (1 + PERMUTATIONS))

    # Empirical Bayes: true effects ~ N(0, tau^2); a noisy cell is pulled harder toward zero.
    dof = (len(offs) - 1) * (len(defs) - 1)
    tau2 = max(spread(table) / dof - float((se.to_numpy() ** 2).mean()), 0.0)
    shrunk = table * tau2 / (tau2 + se ** 2)

    seasons = sorted(g.season.unique())
    corr = None
    if len(seasons) > 1:
        first, last = (fit_table(g[g.season == s], offs, defs).to_numpy().ravel() for s in (seasons[0], seasons[-1]))
        corr = float(np.corrcoef(first, last)[0, 1])
    n_cell = g.groupby(["off_style", "def_style"]).size()
    off_teams = g.drop_duplicates("a").groupby("off_style").size()
    version = f"matchup-v1-{seasons[0]}..{seasons[-1]}"
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("TRUNCATE feat.style_matchup, feat.matchup_meta")
        for o in offs:
            for d in defs:
                cur.execute("INSERT INTO feat.style_matchup (off_style, def_tag, raw_effect, effect, se, n, off_teams, model_version)"
                            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (int(o), d, float(table.loc[o, d]), float(shrunk.loc[o, d]), float(se.loc[o, d]),
                             int(n_cell.get((o, d), 0)), int(off_teams.get(o, 0)), version))
        cur.execute("INSERT INTO feat.matchup_meta (model_version, seasons, n_games, p_value, season_corr, tau)"
                    " VALUES (%s, %s, %s, %s, %s, %s)",
                    (version, seasons, int(g.game_id.nunique()), p_value, corr, float(np.sqrt(tau2))))
    return {"seasons": seasons, "games": int(g.game_id.nunique()), "p_value": round(p_value, 3),
            "season_corr": None if corr is None else round(corr, 2), "tau": round(float(np.sqrt(tau2)), 2)}
