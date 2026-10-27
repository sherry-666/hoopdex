// Chinese labels for the style features stored in feat.player_stats / role profiles.
export const FEATURE_LABELS: Record<string, string> = {
  shot_rim: "篮下出手占比", shot_short_mid: "短中距离占比", shot_long_mid: "长中距离占比",
  shot_corner3: "底角三分占比", shot_atb3: "弧顶三分占比", shot_deep3: "超远三分占比",
  fta_rate: "罚球出手率", usg_pct: "使用率", ast_pct: "助攻率", uast_fgm_pct: "非助攻进球占比",
  oreb_pct: "进攻篮板率", drives_36: "突破 / 36 分钟", touches_36: "触球 / 36 分钟",
  sec_per_touch: "每次触球秒数", drib_per_touch: "每次触球运球", elbow_touch_share: "肘区触球占比",
  post_touch_share: "低位触球占比", paint_touch_share: "油漆区触球占比",
  cs_fga_share: "接球投占比", pullup_fga_share: "急停投占比", screen_ast_36: "掩护助攻 / 36",
  height_in: "身高", weight_lb: "体重", height_cm: "身高 (cm)", weight_kg: "体重 (kg)",
  off_pt_Transition: "快攻", off_pt_Isolation: "单打", off_pt_PRBallHandler: "挡拆持球",
  off_pt_PRRollman: "挡拆顺下", off_pt_Postup: "背身", off_pt_Spotup: "定点",
  off_pt_Handoff: "手递手", off_pt_Cut: "空切", off_pt_OffScreen: "绕掩护", off_pt_OffRebound: "补篮",
  blk_36: "盖帽 / 36", stl_36: "抢断 / 36", dreb_pct: "防守篮板率", rim_dfga_36: "篮下被投 / 36",
  deflections_36: "干扰传球 / 36", charges_36: "造进攻犯规 / 36", contest3_share: "干扰中三分占比",
  contests_36: "干扰出手 / 36", dfga3_share: "被投中三分占比", dfga_lt6_share: "被投中 6ft 内占比",
  speed_def: "防守移动速度",
  def_pt_Isolation: "防单打", def_pt_PRBallHandler: "防挡拆持球", def_pt_PRRollman: "防挡拆顺下",
  def_pt_Postup: "防背身", def_pt_Spotup: "防定点", def_pt_Handoff: "防手递手", def_pt_OffScreen: "防绕掩护",
  pts_36: "得分 / 36", reb_36: "篮板 / 36", ast_36: "助攻 / 36", ts_pct: "真实命中率", fg3_pct: "三分命中率",
  fg3a_36: "三分出手 / 36",
};
export const FEATURE_LABELS_EN: Record<string, string> = {
  shot_rim: "Rim shot share", shot_short_mid: "Short midrange share", shot_long_mid: "Long midrange share",
  shot_corner3: "Corner 3 share", shot_atb3: "Above-the-break 3 share", shot_deep3: "Deep 3 share",
  fta_rate: "Free-throw rate", usg_pct: "Usage", ast_pct: "Assist rate", uast_fgm_pct: "Unassisted FGM share",
  oreb_pct: "Offensive rebound rate", drives_36: "Drives / 36", touches_36: "Touches / 36",
  sec_per_touch: "Seconds per touch", drib_per_touch: "Dribbles per touch", elbow_touch_share: "Elbow touch share",
  post_touch_share: "Post touch share", paint_touch_share: "Paint touch share",
  cs_fga_share: "Catch-and-shoot share", pullup_fga_share: "Pull-up share", screen_ast_36: "Screen assists / 36",
  height_in: "Height", weight_lb: "Weight", height_cm: "Height (cm)", weight_kg: "Weight (kg)",
  off_pt_Transition: "Transition", off_pt_Isolation: "Isolation", off_pt_PRBallHandler: "P&R ball handler",
  off_pt_PRRollman: "P&R roll man", off_pt_Postup: "Post-up", off_pt_Spotup: "Spot-up",
  off_pt_Handoff: "Handoff", off_pt_Cut: "Cut", off_pt_OffScreen: "Off screen", off_pt_OffRebound: "Putback",
  blk_36: "Blocks / 36", stl_36: "Steals / 36", dreb_pct: "Defensive rebound rate", rim_dfga_36: "Rim FGA defended / 36",
  deflections_36: "Deflections / 36", charges_36: "Charges drawn / 36", contest3_share: "3PT share of contests",
  contests_36: "Contests / 36", dfga3_share: "3PT share of shots defended", dfga_lt6_share: "Under-6ft share of shots defended",
  speed_def: "Defensive speed",
  def_pt_Isolation: "Defending isolation", def_pt_PRBallHandler: "Defending P&R ball handler", def_pt_PRRollman: "Defending P&R roll man",
  def_pt_Postup: "Defending post-up", def_pt_Spotup: "Defending spot-up", def_pt_Handoff: "Defending handoff", def_pt_OffScreen: "Defending off screen",
  pts_36: "Points / 36", reb_36: "Rebounds / 36", ast_36: "Assists / 36", ts_pct: "True shooting", fg3_pct: "3PT%",
  fg3a_36: "3PA / 36",
};
const ZH_TO_CODE = Object.fromEntries(Object.entries(FEATURE_LABELS).map(([code, zh]) => [zh, code]));

export const label = (code: string, lang: "zh" | "en" = "zh") =>
  (lang === "en" ? FEATURE_LABELS_EN[code] : FEATURE_LABELS[code]) ?? code;

/** Axis descriptions are stored as Chinese labels joined by "、"; translate each one. */
export const labelList = (zhList: string, lang: "zh" | "en") =>
  lang === "zh" ? zhList : zhList.split("、").map((zh) => label(ZH_TO_CODE[zh] ?? zh, "en")).join(", ");

// Heatmap columns per side, grouped by what they describe.
export const PROFILE_FEATURES: Record<"offense" | "defense", string[]> = {
  offense: ["usg_pct", "ast_pct", "uast_fgm_pct", "drives_36", "drib_per_touch", "pullup_fga_share", "cs_fga_share",
    "shot_rim", "shot_short_mid", "shot_long_mid", "shot_corner3", "shot_atb3", "shot_deep3",
    "off_pt_Isolation", "off_pt_PRBallHandler", "off_pt_PRRollman", "off_pt_Postup", "off_pt_Spotup",
    "off_pt_OffScreen", "off_pt_Handoff", "off_pt_Cut", "off_pt_Transition",
    "post_touch_share", "elbow_touch_share", "oreb_pct", "height_in"],
  defense: ["height_in", "weight_lb", "blk_36", "rim_dfga_36", "dfga_lt6_share", "dreb_pct",
    "dfga3_share", "contest3_share", "stl_36", "deflections_36", "contests_36", "charges_36", "speed_def",
    "def_pt_Isolation", "def_pt_PRBallHandler", "def_pt_PRRollman", "def_pt_Postup", "def_pt_Spotup",
    "def_pt_Handoff", "def_pt_OffScreen"],
};

const BODY_EN: Record<string, string> = {
  Foot: "Foot", Ankle: "Ankle", Knee: "Knee", Hamstring: "Hamstring", Calf: "Calf", Back: "Back", Hip: "Hip", Groin: "Groin",
  Shoulder: "Shoulder", Wrist: "Wrist", Hand: "Hand", Finger: "Finger", Thumb: "Thumb", Elbow: "Elbow", Thigh: "Thigh",
  Quadricep: "Quad", Achilles: "Achilles", Head: "Head", Neck: "Neck", Toe: "Toe", Illness: "Illness", Rest: "Rest",
};
const BODY_ZH: Record<string, string> = {
  Foot: "脚", Ankle: "脚踝", Knee: "膝盖", Hamstring: "腿筋", Calf: "小腿", Back: "背部", Hip: "髋部", Groin: "腹股沟",
  Shoulder: "肩膀", Wrist: "手腕", Hand: "手", Finger: "手指", Thumb: "拇指", Elbow: "手肘", Thigh: "大腿",
  Quadricep: "股四头肌", Achilles: "跟腱", Head: "头部", Neck: "颈部", Toe: "脚趾", Illness: "生病", Rest: "轮休",
};
const SIDE_ZH: Record<string, string> = { Left: "左", Right: "右" };

/** "Left Knee" / "左膝盖": where the injury is, or null when ESPN gives no body part. */
export function injuryWhere(injury: { body_part: string | null; side: string | null }, lang: "zh" | "en"): string | null {
  const part = injury.body_part ? (lang === "zh" ? BODY_ZH : BODY_EN)[injury.body_part] ?? injury.body_part : null;
  const side = injury.side && lang === "zh" ? SIDE_ZH[injury.side] ?? "" : injury.side ?? "";
  return part ? (lang === "zh" ? `${side}${part}` : `${side} ${part}`.trim()) : null;
}
