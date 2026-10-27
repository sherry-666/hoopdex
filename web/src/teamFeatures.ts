// Team offensive-system features (ballstats/team_features.py): [Chinese, English].
export const TEAM_FEATURES: Record<string, [string, string]> = {
  pt_Transition: ["转换进攻", "Transition"], pt_Isolation: ["单打", "Isolation"],
  pt_PRBallHandler: ["挡拆持球", "P&R ball handler"], pt_PRRollman: ["挡拆顺下", "P&R roll man"],
  pt_Postup: ["背身", "Post-ups"], pt_Spotup: ["定点投篮", "Spot-ups"], pt_Handoff: ["手递手", "Handoffs"],
  pt_Cut: ["空切", "Cuts"], pt_OffScreen: ["绕掩护", "Off screens"], pt_OffRebound: ["二次进攻", "Putbacks"],
  passes_100: ["传球", "Passes"], drives_100: ["突破", "Drives"], sec_per_touch: ["持球时间", "Seconds per touch"],
  drib_per_touch: ["运球", "Dribbles per touch"], elbow_100: ["肘区触球", "Elbow touches"],
  post_100: ["低位触球", "Post touches"], paint_100: ["禁区触球", "Paint touches"],
  cs_share: ["接球投篮", "Catch-and-shoot"], pullup_share: ["急停跳投", "Pull-ups"], pace: ["节奏", "Pace"],
  ast_fgm: ["助攻进球", "Assisted baskets"], fb_pts: ["快攻得分", "Fast-break points"],
  paint_pts: ["禁区得分", "Paint points"], mid_pts: ["中距离得分", "Midrange points"],
  fg3a_rate: ["三分出手", "Three-point rate"], rim_share: ["篮下出手", "Rim attempts"],
  paint_share: ["禁区非篮下", "Short paint shots"], mid_share: ["中距离出手", "Midrange attempts"],
  corner3_share: ["底角三分", "Corner threes"], atb3_share: ["弧顶三分", "Above-the-break threes"],
};

// Rows of the style table, grouped.
export const FEATURE_GROUPS: [string, string[]][] = [
  ["战术类型占比", ["pt_PRBallHandler", "pt_PRRollman", "pt_Isolation", "pt_Postup", "pt_Handoff", "pt_Cut",
    "pt_OffScreen", "pt_Spotup", "pt_Transition", "pt_OffRebound"]],
  ["传球与触球", ["passes_100", "ast_fgm", "sec_per_touch", "drib_per_touch", "drives_100", "elbow_100", "post_100", "paint_100"]],
  ["出手与节奏", ["rim_share", "paint_share", "mid_share", "corner3_share", "atb3_share", "fg3a_rate", "cs_share",
    "pullup_share", "paint_pts", "mid_pts", "fb_pts", "pace"]],
];

export const teamFeature = (code: string, lang: "zh" | "en") => TEAM_FEATURES[code]?.[lang === "zh" ? 0 : 1] ?? code;

/** The features where a team stands out most from the league that season. */
export function signature(features: Record<string, number> | null | undefined, n = 3) {
  return Object.entries(features ?? {}).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, n);
}

/** A defensive archetype's name on a team card is its team-level tag. */
export const DEFENSE_TAGS: Record<string, string> = { 护框: "护框型防守", 抢断干扰: "侵略型防守", 外线防投手: "外线封堵型防守", 追防与被针对: "追防型防守" };

/** Background for a z-like value on the red (high) / blue (low) scale shared by the heat tables. */
export const shade = (z: number, full = 1.6) => {
  const a = Math.round(Math.min(1, Math.abs(z) / full) * 85);
  return `color-mix(in srgb, var(${z >= 0 ? "--seq-hi" : "--seq-lo"}) ${a}%, var(--panel))`;
};
export const signed = (z: number, digits = 1) => `${z > 0 ? "+" : z < 0 ? "−" : ""}${Math.abs(z).toFixed(digits)}`;
