"""Do star clutch ability and head-coach quality add to the game predictor? (leave-one-season-out, 2016-17..2025-26)

Frame: margin ~ 1 + minutes-weighted top-9 average rating (last season's) + back-to-back + shrunk form of the last 20
games (scripts/backtest_team_rating.py); each idea adds terms to it.

  clutch  per player and season: clutch TS% (last 5 minutes within 5 points) minus his overall TS%, and the same for
          net rating, shrunk by clutch minutes. First checked for persistence (does last year's edge say anything
          about this year's?), then used for a team's best two players (by rating) or its whole rotation, from the
          last season or the last two pooled.
  coach   the head coach of record of the season (CommonTeamRoster): seasons already spent with this team (tenure),
          head-coaching seasons before this one anywhere since 2008-09 (experience), and how far his earlier teams beat
          what their rosters predicted (points of margin per game, shrunk toward 0).

Result (11982 games, base logloss 0.6184; + = better; se 0.00003-0.0003): nothing helps.
  clutch   a player's clutch edge does not repeat: year-to-year correlation +0.03 (TS) and +0.05 (net rating) over 1491
           player pairs with 40+ clutch minutes in both seasons, so there is no ability to measure. Every variant is
           within +-0.0001 of the base, also in the games the base model calls close (|margin| < 3).
  coach    tenure with the team has an in-sample coefficient of +0.19 points per season (t 3.0) but held out gains
           only +0.0004 (se 0.0003); first-year coaches, head-coaching experience and the coach's earlier record
           against his rosters (persistence +0.09 over 252 team seasons) add nothing. Caveat: the coach of record is the
           one listed for the season, so a mid-season change is credited to the new coach.

Run: .venv/bin/python scripts/backtest_clutch_coach.py   (needs: ballstats collect --groups coaches)
"""

import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).parent))
import backtest_predictor as bp   # noqa: E402
from backtest_team_rating import coefs, evaluate, wavg   # noqa: E402
from ballstats import config   # noqa: E402
from ballstats.collector import result_rows   # noqa: E402

CLUTCH_K = 100.0        # clutch minutes at which a player's edge counts half
COACH_K = 3.0           # earlier seasons at which a coach's record counts half
TENURE_CAP, EXP_CAP = 6, 15


def season_year(s: str) -> int:
    return int(s[:4])


def load_clutch(conn):
    """{(season, pid): dict(min, ts_edge, net_edge)} from the clutch tables against the overall Advanced tables."""
    def table(endpoint, measure):
        out = {}
        for season, body in conn.execute(
                "SELECT params->>'season', body FROM raw.raw_response WHERE endpoint = %s AND status = 'ok'"
                " AND params->>'measure_type_detailed_defense' = %s AND params->>'per_mode_detailed' = 'Totals'"
                " AND NOT params ? 'date_from_nullable'", (endpoint, measure)):
            out[season] = {r["PLAYER_ID"]: r for r in result_rows(body)}
        return out
    clutch, overall = table("LeagueDashPlayerClutch", "Advanced"), table("LeagueDashPlayerStats", "Advanced")
    out = {}
    for season, rows in clutch.items():
        for pid, r in rows.items():
            o = overall.get(season, {}).get(pid)
            if o is None or not r.get("MIN") or r.get("TS_PCT") is None or o.get("TS_PCT") is None:
                continue
            # Advanced MIN is per game: clutch minutes = MIN x GP
            out[(season, pid)] = {"min": float(r["MIN"]) * float(r["GP"] or 0), "ts": 100 * (r["TS_PCT"] - o["TS_PCT"]),
                                  "net": (r["NET_RATING"] or 0.0) - (o["NET_RATING"] or 0.0)}
    return out


def load_coaches(conn):
    """{(season, team): head coach name} (one per team season; the coach of record)."""
    ids = {r[0]: r[1] for r in conn.execute("SELECT DISTINCT params->>'team_id', NULL FROM raw.raw_response WHERE endpoint = 'CommonTeamRoster'")}
    out = {}
    for params, body in conn.execute("SELECT params, body FROM raw.raw_response WHERE endpoint = 'CommonTeamRoster' AND status = 'ok'"):
        hc = [r for r in result_rows(body, "Coaches") if r["COACH_TYPE"] == "Head Coach"]
        if hc:
            tid = int(params["team_id"])
            out[(params["season"], tid)] = hc[0]["COACH_NAME"]
    return out


def main():
    with psycopg.connect(config.DSN) as conn:
        clutch = load_clutch(conn)
        coaches = load_coaches(conn)
        team_id = dict(conn.execute("SELECT DISTINCT team, team_id FROM core.player_season WHERE team_id IS NOT NULL").fetchall())
        rating = pd.DataFrame(conn.execute("SELECT season, player_id, ovr FROM feat.player_rating").fetchall(),
                              columns=["season", "pid", "ovr"]).astype({"ovr": float})
        box = pd.DataFrame(conn.execute("SELECT season, player_id, team, min FROM feat.player_season_box WHERE min IS NOT NULL").fetchall(),
                           columns=["season", "pid", "team", "min"]).astype({"min": float})
        stats = pd.DataFrame(conn.execute("SELECT season, player_id, team, minutes FROM feat.player_stats"
                                          " WHERE season <> 'career' AND team IS NOT NULL").fetchall(),
                             columns=["season", "pid", "team", "min"]).astype({"min": float})
        margin = {(s, t): float(m) for s, t, m in conn.execute(
            "SELECT season, team, avg(team_score - opp_score) FROM live.game WHERE season_type = 2 AND completed"
            " AND team_score IS NOT NULL GROUP BY 1, 2")}
    shrunk = lambda e, m: e * m / (m + CLUTCH_K)

    # ---- clutch persistence: last year's edge vs this year's, players with 40+ clutch minutes in both
    print("clutch persistence (players with 40+ clutch minutes in both seasons)")
    for key in ("ts", "net"):
        a, b, wt = [], [], []
        for (s, pid), v in clutch.items():
            nxt = clutch.get((f"{season_year(s) + 1}-{(season_year(s) + 2) % 100:02d}", pid))
            if nxt and v["min"] >= 40 and nxt["min"] >= 40:
                a.append(v[key]); b.append(nxt[key]); wt.append(min(v["min"], nxt["min"]))
        a, b = np.array(a), np.array(b)
        print(f"  {key:4s} edge: {len(a)} player pairs, year-to-year correlation {np.corrcoef(a, b)[0, 1]:+.3f}")

    # ---- coach tables: tenure, experience
    by_team = defaultdict(dict)          # team id -> {year: coach}
    by_coach = defaultdict(dict)         # coach -> {year: team id}
    for (s, tid), name in coaches.items():
        by_team[tid][season_year(s)] = name
        by_coach[name][season_year(s)] = tid
    tenure = lambda tid, y: next((k for k in range(0, 40) if by_team[tid].get(y - 1 - k) != by_team[tid].get(y)), 0)
    exp = lambda name, y: sum(1 for yy in by_coach[name] if yy < y)

    # roster strength expected for a margin: top 9 by minutes of last season's ratings, per team season (all seasons)
    prior = {s: g.set_index("pid").ovr for s, g in rating.groupby("season")}
    roster, rows = {}, []
    for (s, t), g in box.groupby(["season", "team"]):
        pr = prior.get(f"{season_year(s) - 1}-{season_year(s) % 100:02d}")
        if pr is None or (s, t) not in margin:
            continue
        g = g.sort_values("min", ascending=False).head(9)
        roster[(s, t)] = wavg(g.pid.map(pr).fillna(pr.quantile(0.25)), g["min"])
        rows.append((s, t, roster[(s, t)], margin[(s, t)]))
    rr = pd.DataFrame(rows, columns=["season", "team", "roster", "margin"])
    rr["dev"] = rr.roster - rr.groupby("season").roster.transform("mean")
    slope = float(np.polyfit(rr.dev, rr.margin, 1)[0])
    rr["resid"] = rr.margin - slope * rr.dev
    print(f"\ncoach check: team margin = {slope:.2f} x roster rating gap; residual sd {rr.resid.std():.2f} points per game")
    resid = {(r.season, r.team): r.resid for r in rr.itertuples()}
    # does a coach's residual persist? corr of his mean residual in earlier seasons with this season's
    tid_of = {t: i for t, i in team_id.items()}
    pairs = []
    for (s, t), v in resid.items():
        name = coaches.get((s, tid_of.get(t)))
        if name is None:
            continue
        earlier = [resid[(f"{yy}-{(yy + 1) % 100:02d}", t2)] for yy, tid2 in by_coach[name].items() if yy < season_year(s)
                   for t2 in [k for k, i in tid_of.items() if i == tid2] if (f"{yy}-{(yy + 1) % 100:02d}", t2) in resid]
        if earlier:
            pairs.append((np.mean(earlier), v, len(earlier)))
    p = np.array(pairs)
    print(f"  coach residual persistence: {len(p)} team seasons with an earlier record, correlation {np.corrcoef(p[:, 0], p[:, 1])[0, 1]:+.3f}")

    def extra(y: int) -> dict:
        s = bp.season_str(y)
        pr = rating[rating.season == bp.season_str(y - 1)].set_index("pid").ovr
        out = {}
        for team, g in stats[stats.season == s].groupby("team"):
            g = g.sort_values("min", ascending=False).head(9)
            o = g.pid.map(pr).fillna(pr.quantile(0.25))
            w = g["min"]
            f = {"avg9": wavg(o, w)}
            top2 = list(o.sort_values(ascending=False).index[:2])
            for key in ("ts", "net"):
                def edge(pid, seasons):
                    num = den = 0.0
                    for ss in seasons:
                        v = clutch.get((ss, pid))
                        if v:
                            num += v[key] * v["min"]; den += v["min"]
                    return shrunk(num / den, den) if den else 0.0
                last, last2 = [bp.season_str(y - 1)], [bp.season_str(y - 1), bp.season_str(y - 2)]
                f[f"cl_{key}_top2"] = float(np.mean([edge(g.pid[i], last) for i in top2]))
                f[f"cl_{key}_top2p"] = float(np.mean([edge(g.pid[i], last2) for i in top2]))
                f[f"cl_{key}_all"] = wavg([edge(p_, last) for p_ in g.pid], w)
            tid = team_id.get(team)
            name = coaches.get((s, tid))
            if name is None:
                f.update({"tenure": 0.0, "new": 0.0, "exp": 0.0, "cres": 0.0})
            else:
                f["tenure"] = float(min(tenure(tid, y), TENURE_CAP))
                f["new"] = float(tenure(tid, y) == 0)
                f["exp"] = float(min(exp(name, y), EXP_CAP))
                earlier = [resid[(f"{yy}-{(yy + 1) % 100:02d}", t2)] for yy, tid2 in by_coach[name].items() if yy < y
                           for t2 in [k for k, i in tid_of.items() if i == tid2] if (f"{yy}-{(yy + 1) % 100:02d}", t2) in resid]
                f["cres"] = float(np.sum(earlier) / (len(earlier) + COACH_K)) if earlier else 0.0
            out[team] = f
        return out

    df = bp.build(extra=extra)
    fixed = ["b2b", "sform20"]
    base_cols = ["d_avg9"] + fixed
    base = evaluate(df, base_cols)
    close = np.abs(base["pred"]) < 3    # games the base model sees as close
    print(f"\n{len(df)} games, {close.sum()} close ones (|predicted margin| < 3)")
    print(f"BASE: acc {base['hit'].mean():.3f} brier {base['brier'].mean():.4f} logloss {base['ll'].mean():.4f}\n")
    models = [
        ("-- clutch --", None),
        ("best two: clutch TS edge", ["d_cl_ts_top2"]), ("best two: clutch TS edge, 2 seasons", ["d_cl_ts_top2p"]),
        ("best two: clutch net rating edge", ["d_cl_net_top2"]), ("best two: clutch net edge, 2 seasons", ["d_cl_net_top2p"]),
        ("rotation: clutch TS edge", ["d_cl_ts_all"]), ("rotation: clutch net edge", ["d_cl_net_all"]),
        ("-- coach --", None),
        ("tenure with the team (seasons, cap 6)", ["d_tenure"]), ("first year with the team", ["d_new"]),
        ("head-coaching experience (seasons, cap 15)", ["d_exp"]),
        ("earlier record vs roster (margin pts, shrunk)", ["d_cres"]),
        ("all coach terms", ["d_tenure", "d_new", "d_exp", "d_cres"]),
    ]
    print(f"{'model':46s} {'acc':>6s} {'logloss':>8s} {'vs base':>9s} {'se':>7s} {'seasons+':>9s} {'close games':>12s}")
    for name, cols in models:
        if cols is None:
            print(name)
            continue
        r = evaluate(df, base_cols + cols)
        d = base["ll"] - r["ll"]
        better = sum(d[(df.season == y).to_numpy()].mean() > 0 for y in df.season.unique())
        print(f"{name:46s} {r['hit'].mean():6.3f} {r['ll'].mean():8.4f} {d.mean():+9.5f} {d.std() / math.sqrt(len(d)):7.5f} "
              f"{better:>6d}/10 {d[close].mean():+12.5f}")
    print("\ncoefficients (margin points per unit; t):")
    for cols in (["d_cl_ts_top2"], ["d_cl_net_top2"], ["d_tenure", "d_new", "d_exp"], ["d_cres"]):
        print(" ", {k: v for k, v in coefs(df, base_cols + cols).items() if k in cols})


if __name__ == "__main__":
    main()
