import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "zh" | "en";

/* UI text. Keys are the Chinese source strings; {name} marks a variable. */
const UI_EN: Record<string, string> = {
  // shell
  "首页": "Home", "定位实验室": "Role Lab", "球员名册": "Player Roster", "比赛预测": "Game Predictor", "交易模拟": "Trade Machine",
  "日间版": "Day edition", "夜间版": "Night edition", "主导航": "Main navigation",
  "走错片场了": "Wrong set", "这一页不存在。回首页看看其他球员吧。": "This page doesn't exist. Head home and look at the other players.",
  "选两支球队，看胜率和分差。球员影响力模型完成后上线。": "Pick two teams and see the win probability and margin. Launches once the player impact model is ready.",
  "把球员拖到另一队，看强度和适配度怎么变。比赛预测上线后接着做。": "Drag a player to another team and see how strength and fit change. Comes after the game predictor.",
  "先去定位实验室": "Visit the Role Lab",
  // home
  "HoopDex 用逐回合数据、追踪数据和战术类型，把每个人的打法拆成几种纯粹原型，再把最突出的那几项变成超能力。所有数字都能追到来源。":
    "HoopDex breaks every player's game into a few pure archetypes using play-by-play, tracking and play-type data, then turns their most extreme traits into superpowers. Every number traces back to its source.",
  "找一位球员：Kawhi Leonard": "Find a player: Kawhi Leonard", "搜索球员": "Search players", "搜索": "Search",
  "7 种进攻原型、4 种防守原型，看每名球员是哪几种的混合。": "7 offensive and 4 defensive archetypes. See which mix makes up each player.",
  "每名球员一张卡：超能力、战力数值、风格构成。": "One card per player: superpowers, power stats and style mix.",
  "按上场球员算两队实力，给出胜率和分差。即将登场。": "Team strength from the players on the floor, with win probability and margin. Coming soon.",
  "得分火力最猛的球员": "Top scorers", "（{season} · 每 36 分钟得分）": "({season} · points per 36)",
  // roster
  "{season} 赛季的全部球员。搜名字或球队，按进攻大类筛选。": "Every player of the {season} season. Search by name or team, filter by offensive family.",
  "Stephen Curry、DEN……": "Stephen Curry, DEN…", "搜索球员或球队": "Search players or teams", "排序": "Sort",
  "上场分钟": "Minutes", "得分 / 36": "Points / 36", "真实命中率": "True shooting", "使用率": "Usage",
  "包括不满 500 分钟的球员": "Include players under 500 minutes", "全部": "All", "{n} 名球员": "{n} players",
  "再看 {n} 位": "Show {n} more",
  // roles lab
  "每名球员的打法是几种「纯粹原型」的混合。先选进攻或防守，再点一个原型，看谁最接近它。":
    "Every player's game is a mix of a few pure archetypes. Pick offense or defense, then an archetype, and see who comes closest.",
  "数据：{season} 常规赛，满 500 分钟的球员。": "Data: {season} regular season, players with 500+ minutes.",
  "进攻或防守": "Offense or defense", "进攻": "Offense", "防守": "Defense",
  "聚类视图": "Cluster view",
  "坐标轴是由全部打法特征合成的综合指数，方向选的是让原型分得最开。3D 可以拖动旋转，点一个点打开他的球员档案。":
    "The axes are composite indices built from every style feature, oriented so the archetypes separate as much as possible. Drag to rotate the 3D view; click a dot to open that player's page.",
  "最接近「{name}」的球员": "Closest to {name}", "没有球员在这个原型上占比超过 40%。": "No player is more than 40% this archetype.",
  "风格地图": "Style map", "点的颜色是主原型，越淡越混合。两条轴没有含义，只看远近。":
    "Dot colour is the main archetype; paler means more mixed. The axes have no meaning, only distance does.",
  "原型画像": "Archetype profiles", "原型是最极端的纯粹打法，所以数值比大类更夸张。单位是相对联盟平均的标准差。":
    "Archetypes are the most extreme pure styles, so their values are bolder than the families'. Units are standard deviations from the league average.",
  "坐标轴": "Axes", "可解释指数": "Readable indices", "分得最开": "Most separated", "维度": "Dimensions",
  "只看核心成员（主风格占比 ≥ 50%）": "Core members only (main style ≥ 50%)", "横轴": "X axis", "纵轴": "Y axis", "纵深": "Depth",
  "重置视角": "Reset view", "高：{high}；低：{low}": "High: {high}; low: {low}", "风格构成": "Style mix", "大类": "Family",
  "低于平均 −2σ": "Below average −2σ", "高于平均 +2σ": "Above average +2σ", "大类 · {name}": "Family · {name}",
  "{sigma}，高于联盟平均": "{sigma}, above league average", "{sigma}，低于联盟平均": "{sigma}, below league average",
  // player page
  "← 球员名册": "← Player Roster", "{season} 赛季 · {family}": "{season} season · {family}", "未分类": "Unclassified",
  "{n} 场": "{n} games", "{n} 分钟": "{n} min",
  "样本不足：上场不满 500 分钟，定位和超能力只是投影出来的参考，可信度低。":
    "Small sample: under 500 minutes, so roles and powers are projections with low confidence.",
  "超能力": "Superpowers", "没有哪项打法高出联盟平均 1 个标准差以上：一个均衡型选手。":
    "No trait is more than one standard deviation above the league average: a balanced player.",
  "战力数值": "Power stats", "超过 {p} 的球员": "Better than {p} of players",
  "比较对象：本赛季满 500 分钟的球员。计数类按每 36 分钟换算。": "Compared with this season's players with 500+ minutes. Counts are per 36 minutes.",
  "{side}风格": "{side} style", "大类：{name}": "Family: {name}", "风格最像的球员（同大类）": "Most similar players (same family)",
  "更多数据": "More stats", "指标": "Stat", "数值": "Value",
  "助攻 / 36": "Assists / 36", "篮板 / 36": "Rebounds / 36",
  // seasons and careers
  "赛季": "Season", "球队": "Team", "全部球队": "All teams", "{season}（进行中）": "{season} (in progress)",
  "本赛季刚开始，还没有球员满 500 分钟：下面列出全部球员，定位和超能力都是低置信度的参考。":
    "The season has just started and nobody has 500 minutes yet: every player is listed, and roles and powers are low-confidence.",
  "比较对象：{season} 赛季满 500 分钟的球员。计数类按每 36 分钟换算。": "Compared with {season} players with 500+ minutes. Counts are per 36 minutes.",
  "生涯数据": "Career stats", "常规赛": "Regular season", "季后赛": "Playoffs", "年龄": "Age", "场次": "GP", "首发": "GS",
  "分钟": "MIN", "得分": "PTS", "篮板": "REB", "助攻": "AST", "抢断": "STL", "盖帽": "BLK", "失误": "TOV",
  "投篮%": "FG%", "三分%": "3P%", "罚球%": "FT%", "生涯": "Career", "场均数据；交易赛季显示合并数据。": "Per game; traded seasons show the combined line.",
  "没有季后赛记录。": "No playoff appearances.", "生涯数据还没采集到。": "Career stats haven't been collected yet.",
  "{first} 至 {last}": "{first} to {last}",
  // ratings
  "能力值": "Rating", "{season} 综合评分": "{season} OVR", "这个赛季还没有评分。": "No rating for this season yet.",
  "巅峰评分": "Peak", "生涯评分": "Career", "{n} 个赛季，其中 {q} 季满 500 分钟": "{n} seasons, {q} with 500+ minutes",
  "综合贡献": "Contribution", "PIE {v}：他占场上所有统计事件的份额": "PIE {v}: his share of all box-score events in his games",
  "得分效率与量": "Scoring volume and efficiency", "使用率 {usg}，真实命中率 {ts}（联盟 {lg}）": "Usage {usg}, true shooting {ts} (league {lg})",
  "在场表现": "On-court", "他在场时球队每 100 回合净胜 {net} 分": "Team net {net} points per 100 possessions with him on the floor",
  "样本权重 {w}（{min} 分钟）：样本越少，评分越向替补水平靠拢。": "Sample weight {w} ({min} min): the smaller the sample, the closer to replacement level.",
  "本赛季还早，按 {s} 赛季的标准换算。": "It's early in the season, so the scale comes from {s}.",
  "各赛季评分": "Rating by season", "各赛季评分（黄色区域是巅峰三季）": "Rating by season (yellow: peak three seasons)",
  "评分是怎么算的？": "How is the rating built?",
  "每个赛季用联盟官方的全员数据，算三项指标：综合贡献（PIE，占场上统计事件的份额）、得分效率与量（使用率 × 真实命中率高出联盟的部分，再加上球权本身的价值）、在场表现（他在场时球队的净效率，按上场时间打折，因为它受队友影响很大）。":
    "Each season, from the league's full player tables, three measures: contribution (PIE, his share of box-score events), scoring volume and efficiency (usage times true shooting above league average, plus credit for usage itself) and on-court (team net rating with him playing, discounted by minutes because teammates drive much of it).",
  "每项都和同赛季满 500 分钟的球员比，换成标准差（σ），按 40% / 40% / 20% 加权合成。": "Each is compared with that season's 500+ minute players, turned into standard deviations (σ) and combined 40% / 40% / 20%.",
  "按上场时间做收缩：分钟越少，越向替补水平靠拢，避免几场比赛就打出 95 分。": "Shrunk by minutes: the fewer minutes, the closer to replacement level, so a few games can't produce a 95.",
  "换算成 2K 式分数：77 + 6.5 × σ，范围 40–99。联盟中位数约 75，前 10% 约 82 以上，最顶尖接近 99。": "Scaled 2K-style: 77 + 6.5 × σ, from 40 to 99. The league median is about 75, the top 10% about 82+, the very best near 99.",
  "巅峰评分 = 生涯中连续三个满 500 分钟赛季的最高平均；生涯评分 = 70% 巅峰 + 30% 各赛季按分钟加权的平均。": "Peak = the best average over three 500+ minute seasons in a row; career = 70% peak + 30% the minutes-weighted average over all seasons.",
  "这是第一版（只用 box score）。它偏爱篮板多、出手效率高的内线；之后会换成考虑队友和对手的影响力模型（RAPM）。每个赛季都在当季内排名，所以不同年代可以直接比较。":
    "This is version 1, box score only. It favours rebounding, efficient bigs; it will move to the impact model (RAPM), which accounts for teammates and opponents. Each season is ranked within itself, so eras compare directly.",
  "综合评分": "OVR",
  // site
  "HoopDex 是独立的球迷数据项目，与 NBA 及各球队没有关联。数据来自 stats.nba.com。":
    "HoopDex is an independent fan project, not affiliated with the NBA or its teams. Data from stats.nba.com.",
  "{name} 的打法原型与超能力 · NBA {season}": "{name}: archetypes and superpowers · NBA {season}",
  "生涯视图：每名球员各赛季的打法按上场分钟加权平均，至少有一季满 500 分钟才算核心样本。":
    "Career view: each player's seasons averaged by minutes played; a player counts as a core sample with at least one 500-minute season.",
  "本赛季刚开始，还没有球员满 500 分钟：下面显示全部球员，位置和定位都是低置信度的参考。":
    "The season has just started and nobody has 500 minutes yet: everyone is shown, and positions and roles are low-confidence.",
  // teams
  "建队思路": "Team-building style", "轮换 OVR": "Rotation OVR",
  "主力轮换": "Main rotation", "{n} 支球队": "{n} teams",
  "按每队上场时间最多的 9 名球员，把他们的打法原型按分钟加权，得出球队的风格；再把风格相近的球队归成 5 种建队思路。打法是连续的，归类表示「最接近」，不是严格的派系。":
    "Each team's style is the minutes-weighted archetype mix of its 9 players with the most minutes; teams with similar styles are grouped into 5 team-building styles. Styles are a continuum, so a group means closest to, not a strict faction.",
  "本赛季刚开始，轮换和风格还会变化。": "The season has just started; rotations and styles will still change.",
  "交易过的球员算在他最后效力的球队。": "Traded players count for the team they finished with.",
  "挡拆持球手搭配顺下的篮下终结者，外线是跑动射手。": "A pick-and-roll ball handler with a rolling rim finisher, and movement shooters outside.",
  "进攻通过内线组织者展开：高位、低位传球和手递手，配挡拆和跑动射手。": "Offense runs through an interior hub: high- and low-post passing and handoffs, with pick-and-roll and movement shooters.",
  "突破和单打直冲篮筐，篮下终结多；定点射手和挡拆用得少。": "Drives and isolations attack the rim with lots of finishing; few spot-up shooters or pick-and-rolls.",
  "一到两名单打或挡拆的持球核心，周围摆满定点射手。": "One or two isolation or pick-and-roll creators surrounded by spot-up shooters.",
  "多名突破组织者冲击禁区，再分给底角和定点射手。": "Several drive-and-dish creators attack the paint and kick out to corner and spot-up shooters.",
  // comic pieces
  "{name} 的漫画形象": "{name} comic portrait", "{name}：漫画形象待绘制": "{name}: comic portrait not drawn yet", "漫画形象绘制中": "Portrait coming soon",
  "等级 {g}": "Grade {g}", "依据：{label} {value}，高于联盟平均 {z} 个标准差": "Based on: {label} {value}, {z} standard deviations above league average",
  "正在加载{what}……": "Loading {what}…", "数据": "data", "球员": "players", "名册": "roster", "定位模型": "role model", "球员档案": "player page",
  "出错了": "Something went wrong",
  "数据没能加载：{msg}。检查 API 服务（端口 8000）是否在运行，然后刷新。": "Couldn't load the data: {msg}. Check that the API server (port 8000) is running, then refresh.",
  "没有这名球员": "No such player",
};

/* Names that come from the data (role model, axes). Keys are the stored Chinese names. */
const NAMES_EN: Record<string, string> = {
  "单打得分手": "Iso Scorer", "突破组织": "Drive-and-Dish Creator", "定点射手": "Spot-up Shooter", "无球射手": "Movement Shooter",
  "内线组织者": "Interior Hub", "挡拆发起者": "Pick-and-Roll Engine", "篮下终结者": "Rim Finisher",
  "追防与被针对": "Chaser / Targeted", "外线防投手": "Perimeter Contester", "护框": "Rim Protector", "抢断干扰": "Disruptor",
  "内线": "Interior", "无球侧翼 / 射手": "Off-ball Wings / Shooters", "持球创造者": "Creators", "外线": "Perimeter",
  "挡拆顺下": "Pick-and-Roll Rim", "内线枢纽": "Interior Hub Offense", "冲击篮下": "Rim Attack", "持球核心 + 空间": "Star Creator + Spacing",
  "突破分球": "Drive and Kick", "护框型防守": "Rim-protection defense", "侵略型防守": "Disruptive defense",
  "外线封堵型防守": "Perimeter-contest defense", "追防型防守": "Chase defense",
  "持球创造指数（低 = 接球投射）": "Creation index (low = catch-and-shoot)", "内线终结指数": "Interior finishing index",
  "低位组织指数": "Post hub index", "外线指数（低 = 护框）": "Perimeter index (low = rim protection)",
  "追防指数（低 = 挡拆大个）": "Chase index (low = pick-and-roll big)", "抢断干扰指数": "Disruption index",
};

/* Superpowers by feature code, mirroring ballstats/powers.py. */
export const POWERS_EN: Record<string, [string, string]> = {
  shot_long_mid: ["Midrange Domain", "Step into the midrange and every shot feels like a paused frame."],
  off_pt_Isolation: ["Iso Barrier", "Clear one side and one-on-one mode switches on."],
  drives_36: ["Gale Drive", "A first step so quick defenders only see an afterimage."],
  off_pt_PRBallHandler: ["Screen Puppeteer", "One screen is enough to pull a whole defense apart."],
  ast_pct: ["Court Vision", "Passing lanes light up in his eyes before they open."],
  uast_fgm_pct: ["Self Creator", "No feed needed: he makes his own looks."],
  pullup_fga_share: ["Pull-up Strike", "Stops on a dime mid-dribble and rises into the shot."],
  shot_deep3: ["Logo Sniper", "Even near half court he's in range."],
  off_pt_OffScreen: ["Phantom Runner", "Weaves through screen after screen and fires on the catch."],
  off_pt_Handoff: ["Handoff Chain", "Every handoff is a threat from three."],
  shot_corner3: ["Corner Sniper", "Park him in the corner and it's an automatic three-point threat."],
  cs_fga_share: ["Catch and Fire", "The ball is in the air the moment it reaches him."],
  off_pt_Spotup: ["Spot-up Cannon", "Stands still and still stretches the defense."],
  shot_rim: ["Paint Gravity", "Every shot happens at the rim."],
  off_pt_Cut: ["Ghost Cut", "Defender turns his head and he's already under the basket."],
  oreb_pct: ["Rebound Vacuum", "Missed shots always find their way to him."],
  off_pt_OffRebound: ["Second Chance", "Missed the first one? He puts in the second."],
  off_pt_Postup: ["Post Cannon", "One back-down and defenders give ground."],
  post_touch_share: ["Lord of the Post", "The low block is his throne."],
  elbow_touch_share: ["Elbow Command Tower", "Runs the whole team from the free-throw line extended."],
  off_pt_PRRollman: ["Rolling Express", "Sets the screen and charges the rim. Nobody stops the train."],
  screen_ast_36: ["Human Wall", "His screens are his teammates' open looks."],
  off_pt_Transition: ["Fast-break Flash", "One turnover and two seconds later it's a bucket."],
  fta_rate: ["Foul Magic", "The moment there's contact, the free-throw line is waiting."],
  blk_36: ["Swat Hand", "However high the release, he sends it back."],
  rim_dfga_36: ["No-fly Zone", "With him at the rim, nobody wants to take off."],
  contests_36: ["Everywhere at Once", "There's a hand in front of every shot."],
  deflections_36: ["Interceptor", "His fingertips are always in the passing lane."],
  stl_36: ["Master Thief", "Loosen the dribble for a second and the ball changes hands."],
  charges_36: ["Iron Body", "He stands his ground and the driver gets the offensive foul."],
  speed_def: ["Shadow Step", "However many screens you run, you can't shake him."],
  contest3_share: ["Three-point Lockdown", "A shooter raises the ball and he's already in his face."],
  dreb_pct: ["Backboard Keeper", "Second chances get confiscated."],
  def_pt_Isolation: ["Lockdown Smith", "Go at him one-on-one and you usually come away empty."],
};

interface LangCtx { lang: Lang; setLang: (l: Lang) => void; t: (zh: string, vars?: Record<string, string | number>) => string; name: (zh: string | null | undefined) => string }
const Ctx = createContext<LangCtx | null>(null);

function fill(s: string, vars?: Record<string, string | number>) {
  return vars ? s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? "")) : s;
}

export function LangProvider({ children }: { children: ReactNode }) {
  // ?lang=en in the URL wins (it's the English page search engines index), then the saved choice.
  const [lang, setLangState] = useState<Lang>(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    if (fromUrl === "en" || fromUrl === "zh") return fromUrl;
    try { return (localStorage.getItem("lang") as Lang) || "zh"; } catch { return "zh"; }
  });
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem("lang", l); } catch { /* storage blocked */ }
    const url = new URL(window.location.href);
    if (url.searchParams.has("lang")) {
      if (l === "en") url.searchParams.set("lang", "en"); else url.searchParams.delete("lang");
      window.history.replaceState(window.history.state, "", url);
    }
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [lang]);
  const value = useMemo<LangCtx>(() => ({
    lang, setLang,
    t: (zh, vars) => fill(lang === "en" ? UI_EN[zh] ?? zh : zh, vars),
    name: (zh) => {
      if (!zh) return "";
      if (lang === "zh") return zh;
      if (zh.includes(" + ")) return zh.split(" + ").map((p) => NAMES_EN[p] ?? p).join(" + ");
      const axis = zh.match(/^判别轴 (\d)$/);
      return axis ? `Discriminant axis ${axis[1]}` : NAMES_EN[zh] ?? zh;
    },
  }), [lang, setLang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

const SITE_TITLE = { zh: "HoopDex · NBA 球员图鉴：打法原型、超能力与数据", en: "HoopDex · NBA Player Dex: archetypes, superpowers and stats" };

/** Sets the browser tab / search title: "<page> · HoopDex", or the site title on its own. */
export function usePageTitle(title?: string) {
  const { lang } = useLang();
  useEffect(() => {
    document.title = title ? `${title} · HoopDex` : SITE_TITLE[lang];
  }, [title, lang]);
}

export function useLang(): LangCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLang outside LangProvider");
  return ctx;
}
