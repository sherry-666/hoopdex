"""Export the role model for the dashboard. Usage: export_roles.py SEASON OUT_DIR

Writes three JSON files of row objects:
  role_players.json  one row per player and side: family, style mix, map position
  role_types.json    one row per family/archetype and feature: its z-score profile
  role_stats.json    one row per player: raw stat values in readable units + roles
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ballstats import db, features, roles
from ballstats.views import FEATURE_LABELS, cluster_axes, map_coords, shown_players, stat_values

SIDE_LABEL = {"offense": "进攻", "defense": "防守"}


def mix_text(w: pd.Series, names: dict[int, str]) -> str:
    parts = [f"{names[int(i)]} {v:.0%}" for i, v in w.sort_values(ascending=False).items() if v >= 0.1]
    return " · ".join(parts)


def main(season: str, out_dir: Path) -> None:
    conn = db.connect()
    info, off, de = features.build(conn, season)
    players, types, role_cols, axes_rows = [], [], {}, []
    for side, X in (("offense", off), ("defense", de)):
        fit = roles.fit_side(side, X, info["min"])
        fam_names, arch_names = roles.type_names(season, fit)
        if not arch_names:
            raise SystemExit(f"role_names.json has no names for {fit.model_version}")
        label = SIDE_LABEL[side]
        shown = shown_players(fit, info["min"])
        xy = map_coords(fit, shown).to_numpy()
        scores, meta = cluster_axes(side, X, fit, shown)
        axes_rows.extend({"key": f"{label}-{m['axis']}", "side": label, **m} for m in meta)
        for pid, (x, y) in zip(shown, xy):
            w = fit.weights.loc[pid]
            top = int(w.idxmax())
            row = {
                "key": f"{label}-{pid}", "side": label, "player_id": int(pid),
                "name": info.at[pid, "name"], "team": info.at[pid, "team"],
                "minutes": int(round(info.at[pid, "min"])), "in_fit": bool(fit.in_fit[pid]),
                "family": fam_names[int(fit.families[pid])], "top": arch_names[top],
                "top_weight": round(float(w.max()), 3), "style": roles.style_label(w, arch_names),
                "mix": mix_text(w, arch_names), "x": round(float(x), 3), "y": round(float(y), 3),
            }
            for a, v in w.items():
                row[f"w{a}"] = round(float(v), 3)
            for col, v in scores.loc[pid].items():
                row[col] = round(float(v), 3)
            players.append(row)
            role_cols.setdefault(pid, {}).update({
                f"{side[:3]}_family": row["family"], f"{side[:3]}_style": row["style"],
                f"{side[:3]}_top": row["top"],
            })
        counts = {"family": fit.families[fit.in_fit].value_counts(),
                  "archetype": fit.weights[fit.in_fit].idxmax(axis=1).value_counts()}
        for level, profiles, names in (("archetype", fit.archetype_profiles, arch_names),
                                       ("family", fit.family_profiles, fam_names)):
            for type_id, prof in profiles.iterrows():
                for feat, z in prof.items():
                    types.append({
                        "key": f"{label}-{level}-{type_id}-{feat}", "side": label, "level": level,
                        "type_id": int(type_id), "name": names[int(type_id)],
                        "players": int(counts[level].get(type_id, 0)),
                        "feature": FEATURE_LABELS.get(feat, feat), "feature_code": feat,
                        "z": round(float(np.clip(z, -3, 3)), 2),
                    })
        print(side, fit.model_version, len(shown), "players shown")

    # Raw values in readable units for the stat scatter.
    raw = stat_values(info, off, de)
    stats = []
    for pid in sorted(role_cols):
        row = {"player_id": int(pid), "name": info.at[pid, "name"], "team": info.at[pid, "team"],
               "minutes": int(round(info.at[pid, "min"])), "in_fit": bool(info.at[pid, "min"] >= roles.MIN_MINUTES),
               **role_cols[pid]}
        for col, value in raw.loc[pid].items():
            row[col] = None if pd.isna(value) else round(float(value), 4)
        stats.append(row)

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("role_players", players), ("role_types", types), ("role_stats", stats),
                       ("role_axes", axes_rows)):
        (out_dir / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False))
        print(name, len(rows), "rows")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
