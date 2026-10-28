"""Transition values for the season in progress.

Early in a season a few games say little, so model outputs for the ongoing season are a
weighted blend of this season and last season:

    value = w x this season + (1 - w) x last season

  players   w = minutes / (minutes + PLAYER_MIN)   170 min -> 22%, 600 -> 50%, 1800 -> 75%
  teams     w = games / (games + TEAM_GP)          5 games -> 20%, 20 -> 50%, 60 -> 75%

Blended: ratings (OVR / offense / defense), archetype mixes and style labels, superpowers,
team offensive systems and team ratings. Box-score stats are never blended; they stay the
season's actual numbers. Players without a previous season (rookies) are not blended.

Ratings look back further than one season: the "last season" side is a minutes-weighted average
of up to the three previous seasons, each decayed by PRIOR_DECAY per season back. A season a
player missed (injury) or barely played carries almost no weight, so a player coming back from
a lost year is judged on the seasons before it. Looking back stops at the first season with
500+ minutes: a full last season is enough on its own. Roles and superpowers still use last season only.
"""

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

PLAYER_MIN = 600
TEAM_GP = 20
PRIOR_SEASONS = 3       # ratings look back up to this many seasons
PRIOR_DECAY = 0.6       # each season further back counts this much less: 1, 0.6, 0.36
ONGOING_MAX_GP = 70     # a season is still in progress while nobody has played this many games


def previous(season: str) -> str:
    y = int(season[:4]) - 1
    return f"{y}-{(y + 1) % 100:02d}"


def prior_seasons(season: str) -> list[tuple[str, float]]:
    """The seasons a rating looks back to, newest first, with their decay."""
    out = []
    for k in range(PRIOR_SEASONS):
        season = previous(season)
        out.append((season, PRIOR_DECAY ** k))
    return out


def player_weight(minutes: float) -> float:
    return float(minutes) / (float(minutes) + PLAYER_MIN)


def team_weight(games: float) -> float:
    return float(games) / (float(games) + TEAM_GP)


def ongoing_season(conn: psycopg.Connection) -> str | None:
    """The newest season, if it is still in progress."""
    row = conn.execute("SELECT season, max(gp) FROM feat.player_stats WHERE season <> 'career'"
                       " GROUP BY season ORDER BY season DESC LIMIT 1").fetchone()
    return row[0] if row and row[1] < ONGOING_MAX_GP else None


def blend_roles(conn: psycopg.Connection) -> dict:
    """Blend the ongoing season's archetype mixes with last season's. Idempotent: the
    season's own mix is kept in raw_weights and every run blends from it."""
    from ballstats import roles

    season = ongoing_season(conn)
    if season is None:
        return {"season": None}
    prior = previous(season)
    arch = {side: {int(t): n for t, n in conn.execute(
        "SELECT type_id, name FROM feat.role_type WHERE season = %s AND side = %s AND level = 'archetype'", (season, side))}
        for side in ("offense", "defense")}
    rows = conn.execute(
        """
        SELECT r.player_id, r.side, coalesce(r.raw_weights, r.weights), r.family_id, r.family_name,
               s.minutes, p.weights, p.family_id, p.family_name
        FROM feat.player_role r
        JOIN feat.player_stats s USING (season, player_id)
        LEFT JOIN feat.player_role p ON p.season = %s AND p.player_id = r.player_id AND p.side = r.side
        WHERE r.season = %s
        """, (prior, season)).fetchall()
    n = 0
    with conn.transaction(), conn.cursor() as cur:
        for pid, side, raw, fam, fam_name, minutes, prior_w, prior_fam, prior_fam_name in rows:
            if prior_w is None:
                cur.execute("UPDATE feat.player_role SET raw_weights = NULL, blend_weight = NULL, prior_season = NULL,"
                            " weights = %s WHERE season = %s AND player_id = %s AND side = %s",
                            (Jsonb(raw), season, pid, side))
                continue
            w = player_weight(minutes)
            mix = pd.Series({int(k): w * float(raw.get(k, 0)) + (1 - w) * float(prior_w.get(k, 0))
                             for k in set(raw) | set(prior_w)})
            mix = mix / mix.sum()
            top = int(mix.idxmax())
            # Families come from the embedding, which isn't blended: follow whichever season weighs more.
            f_id, f_name = (fam, fam_name) if w >= 0.5 else (prior_fam, prior_fam_name)
            cur.execute(
                "UPDATE feat.player_role SET raw_weights = %s, weights = %s, top_archetype_id = %s, top_archetype_name = %s,"
                " top_weight = %s, style_label = %s, family_id = %s, family_name = %s, blend_weight = %s, prior_season = %s"
                " WHERE season = %s AND player_id = %s AND side = %s",
                (Jsonb(raw), Jsonb({str(k): round(float(v), 4) for k, v in mix.items()}), top, arch[side].get(top),
                 float(mix.max()), roles.style_label(mix, arch[side]), f_id, f_name, round(w, 3), prior,
                 season, pid, side))
            n += 1
    return {"season": season, "prior": prior, "blended": n}
