"""Comic-book superpowers derived from a player's most extreme style stats.

A power is a feature where the player sits far above the league (z >= MIN_Z among
fit players), named from a fixed table. The grade follows the z-score. Purely a
presentation layer over real numbers: every power quotes the stat behind it.
"""

from dataclasses import asdict, dataclass

MIN_Z = 1.0
GRADES = ((2.5, "S"), (1.8, "A"), (1.0, "B"))

# feature -> (power name, one-line description)
OFFENSE = {
    "shot_long_mid": ("中距离领域", "踏进中距离，出手像按下了暂停键。"),
    "off_pt_Isolation": ("一对一结界", "清空一侧，单挑模式自动开启。"),
    "drives_36": ("疾风突破", "第一步快到防守人只看见残影。"),
    "off_pt_PRBallHandler": ("挡拆操控者", "一个掩护，就能把整套防守拆开。"),
    "ast_pct": ("全场视野", "传球路线在他眼里提前亮起。"),
    "uast_fgm_pct": ("自主创造", "不需要队友喂球，自己造出机会。"),
    "pullup_fga_share": ("急停跳投", "运球中途说停就停，拔起就投。"),
    "shot_deep3": ("Logo 狙击", "半场线附近也在射程之内。"),
    "off_pt_OffScreen": ("无影跑位", "绕过一层层掩护，接球时已经出手。"),
    "off_pt_Handoff": ("手递手连环", "每一次手递手都是一次三分威胁。"),
    "shot_corner3": ("底角狙击手", "站在底角，就是一道三分保险。"),
    "cs_fga_share": ("接球即发", "球到手的那一刻已经在空中。"),
    "off_pt_Spotup": ("定点炮台", "原地不动，也能把防守拉开。"),
    "shot_rim": ("禁区引力", "所有出手都在篮下发生。"),
    "off_pt_Cut": ("幽灵空切", "防守一回头，他已经在篮下。"),
    "oreb_pct": ("篮板吸尘器", "投丢的球总会落到他手里。"),
    "off_pt_OffRebound": ("二次进攻", "第一次没进？第二次补进。"),
    "off_pt_Postup": ("低位重炮", "背身一靠，对手只能后退。"),
    "post_touch_share": ("背身领主", "低位是他的王座。"),
    "elbow_touch_share": ("高位指挥塔", "罚球线两侧调度全队。"),
    "off_pt_PRRollman": ("顺下列车", "掩护之后直冲篮筐，没人拦得住。"),
    "screen_ast_36": ("人墙掩护", "他的掩护，就是队友的空位。"),
    "off_pt_Transition": ("快攻闪电", "一次转换，两秒后已经得分。"),
    "fta_rate": ("造犯规魔术", "身体对抗一出现，罚球线就在等他。"),
}
DEFENSE = {
    "blk_36": ("封盖之手", "出手点再高，也会被他扇下来。"),
    "rim_dfga_36": ("禁飞区", "他在篮下，对手就不敢起跳。"),
    "contests_36": ("无处不在", "每一次出手面前都有他的手。"),
    "deflections_36": ("截击触手", "传球路线上总有他的指尖。"),
    "stl_36": ("抢断大盗", "运球稍一松懈，球就换了主人。"),
    "charges_36": ("钢铁之躯", "站定不动，撞上来的人吃进攻犯规。"),
    "speed_def": ("追影步", "绕再多掩护，也甩不掉他。"),
    "contest3_share": ("三分封锁", "射手一抬手，他已经扑到面前。"),
    "dreb_pct": ("后场守门员", "对手的第二次机会被他没收。"),
    "def_pt_Isolation": ("单防锁匠", "单挑找上他，往往无功而返。"),
}


@dataclass
class Power:
    side: str          # offense | defense
    feature: str
    name: str
    description: str
    grade: str
    z: float
    value: float | None


def grade_for(z: float) -> str:
    return next(g for cut, g in GRADES if z >= cut)


def powers_for(z_by_feature: dict[str, float], values: dict[str, float | None],
               limit: dict[str, int] | None = None) -> list[dict]:
    """Best powers per side, strongest first. z_by_feature uses the stat keys of
    feat.player_stats; features without a table entry are ignored."""
    limit = limit or {"offense": 2, "defense": 1}
    out = []
    for side, table in (("offense", OFFENSE), ("defense", DEFENSE)):
        ranked = sorted(((z_by_feature.get(f), f) for f in table if z_by_feature.get(f) is not None),
                        reverse=True)
        for z, f in ranked[:limit[side]]:
            if z < MIN_Z:
                break
            name, desc = table[f]
            out.append(asdict(Power(side, f, name, desc, grade_for(z), round(z, 2), values.get(f))))
    return out
