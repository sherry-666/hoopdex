import { useLocation, useNavigate } from "react-router-dom";
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "zh" | "en";

/* UI text. Keys are the Chinese source strings; {name} marks a variable. */
const UI_EN: Record<string, string> = {
  // shell
  "今天起三天的比赛，标出预测会赢的一方和胜率。点进去看两队对比。": "Games from today through the next two days, with the predicted winner and win probability. Open one for the side-by-side.",
  "这一天没有比赛。": "No games on this day.", "已结束": "Final", "阵容": "Roster", "预测": "Prediction", "预计分差": "Expected margin", "主队 {pct}%": "Home {pct}%",
  "球队评分差（按当天能出战的球员）": "Team rating gap (players able to play that day)",
  "阵容适配（头部球员，≥{n}）": "Lineup fit (top players, ≥{n})", "主力克制（头部球员，≥{n}）": "Star matchup (top players, ≥{n})",
  "合计（主队减客队）": "Total (home minus away)", "头部球员": "Top players", "当天无法出战": "out that day",
  "阵容适配和主力克制在历史回测里几乎没有预测力，这里只按四分之一计入，各自最多 ±1.5 分。": "Lineup fit and star matchup showed almost no predictive power in backtests, so they count at a quarter and at most ±1.5 points each.", "最强球员": "Best players", "场均篮板": "Rebounds per game", "场均助攻": "Assists per game", "球队对比": "Team comparison", "进攻效率": "Offensive rating", "防守效率": "Defensive rating", "场均得分": "Points per game", "场均失分": "Points allowed per game", "今天": "Today", "赛程": "the schedule",
  "首页": "Home", "定位实验室": "Role Lab", "球员名册": "Player Roster", "比赛预测": "Game Predictor",
  "日间版": "Day edition", "夜间版": "Night edition", "主导航": "Main navigation",
  "走错片场了": "Wrong set", "这一页不存在。回首页看看其他球员吧。": "This page doesn't exist. Head home and look at the other players.",
  "选两支球队，看胜率和分差。球员影响力模型完成后上线。": "Pick two teams and see the win probability and margin. Launches once the player impact model is ready.",
  "把球员拖到另一队，看强度和适配度怎么变。比赛预测上线后接着做。": "Drag a player to another team and see how strength and fit change. Comes after the game predictor.",
  "先去定位实验室": "Visit the Role Lab",
  // home
  "Hoopedia 用逐回合数据、追踪数据和战术类型，把每个人的打法拆成几种纯粹原型，再把最突出的那几项变成超能力。所有数字都能追到来源。":
    "Hoopedia breaks every player's game into a few pure archetypes using play-by-play, tracking and play-type data, then turns their most extreme traits into superpowers. Every number traces back to its source.",
  "找一位球员：Kawhi Leonard": "Find a player: Kawhi Leonard", "搜索球员": "Search players", "搜索": "Search",
  "7 种进攻原型、4 种防守原型，看每名球员是哪几种的混合。": "7 offensive and 4 defensive archetypes. See which mix makes up each player.",
  "每名球员一张卡：超能力、战力数值、风格构成。": "One card per player: superpowers, power stats and style mix.",
  "按上场球员算两队实力，给出胜率和分差。即将登场。": "Team strength from the players on the floor, with win probability and margin. Coming soon.",
  "得分火力最猛的球员": "Top scorers", "（{season} · 每 36 分钟得分）": "({season} · points per 36)",
  "名人堂": "Hall of Fame", "冠军": "Titles", "全明星": "All-Star", "（荣誉与能力 · 生涯总评）": "(honors and ability · career rating)", "生涯最强球员": "Best players of all time", "（生涯总评）": "(career rating)", "赛季最佳球员": "Best players of the season", "（{season} · 总评）": "({season} · overall rating)",
  "赛季最佳进攻球员": "Best offensive players", "（{season} · 进攻评分）": "({season} · offense rating)",
  "赛季最佳防守球员": "Best defensive players", "（{season} · 防守评分）": "({season} · defense rating)",
  // injuries and recent games
  "伤停": "Out", "出战成疑": "Day-to-day", "预计 {date} 前后复出": "Expected back around {date}",
  "来源 ESPN，{date} 更新。": "Source: ESPN, updated {date}.", "近期比赛": "Recent games", "日期": "Date", "对手": "Opponent",
  "比分": "Score", "投篮": "FG", "三分": "3PT", "胜": "W", "负": "L", "未出场": "Did not play",
  "每天自动更新，来源 ESPN；只含最近同步到的比赛。": "Updated daily from ESPN; only games synced so far.",
  // rankings
  "排名": "Rankings", "{season} 赛季东西部排名和球员数据排行。": "{season} conference standings and player stat leaders.",
  "东部": "Eastern Conference", "西部": "Western Conference", "胜率": "PCT", "胜场差": "GB", "近10场": "L10", "连续": "Streak",
  "球员排名": "Player rankings", "姓名": "Player", "攻 / 守": "OFF / DEF",
  "三分命中": "3PM",
  "{season} 赛季常规赛；命中数要达到球队每场平均的门槛才入榜。": "{season} regular season; shooters need a minimum number of makes per team game.",
  "{season} 赛季常规赛场均数据；至少打了球队 70% 的比赛（{n} 场）。": "{season} regular-season per-game averages; at least 70% of the team's games ({n}).",
  "这个赛季还没有这项数据。": "No data for this stat in this season yet.",
  "联盟最佳战绩": "League-best record", "本区第一": "Conference #1 seed", "分区冠军": "Division champion", "晋级季后赛": "Playoffs",
  "晋级季后赛（经附加赛）": "Playoffs (via play-in)", "晋级附加赛": "Play-in", "无缘季后赛": "Missed playoffs",
  "赛季刚开始，评分是本赛季与上赛季的合成值；上场不满 60 分钟的球员不参与。": "Early in the season: ratings blend this season with last, and players under 60 minutes are left out.",
  "{season} 赛季满 500 分钟的球员，按评分排序。": "Players with 500+ minutes in {season}, sorted by rating.",
  "每天自动更新，来源 ESPN，{date} 更新。": "Updated daily from ESPN, last on {date}.",
  // honors
  "荣誉": "Honors", "球队荣誉": "Team honors", "总冠军": "Championships", "联盟冠军": "Conference titles", "退役球衣": "Retired numbers",
  "名人堂球员": "Hall of Famers", "{k} 阵 ×{n}": "Team {k} ×{n}",
  "来源 stats.nba.com；赛季以 {ex} 这样的简写显示。": "Source: stats.nba.com; seasons shown as {ex}.", "来源 stats.nba.com。": "Source: stats.nba.com.",
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
  "巅峰评分": "Peak", "三季平均": "3-season avg", "生涯评分": "Career", "{n} 个赛季，其中 {q} 季满 500 分钟": "{n} seasons, {q} with 500+ minutes",
  "综合贡献": "Contribution", "PIE {v}：他占场上所有统计事件的份额": "PIE {v}: his share of all box-score events in his games",
  "得分效率与量": "Scoring volume and efficiency", "使用率 {usg}，真实命中率 {ts}（联盟 {lg}）": "Usage {usg}, true shooting {ts} (league {lg})",
  "在场表现": "On-court", "他在场时球队每 100 回合净胜 {net} 分": "Team net {net} points per 100 possessions with him on the floor",
  "样本权重 {w}（{min} 分钟）：样本越少，评分越向替补水平靠拢。": "Sample weight {w} ({min} min): the smaller the sample, the closer to replacement level.",
  "本赛季还早，按 {s} 赛季的标准换算。": "It's early in the season, so the scale comes from {s}.",
  "各赛季评分": "Rating by season",
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
  "Hoopedia 是独立的球迷数据项目，与 NBA 及各球队没有关联。数据来自 stats.nba.com。":
    "Hoopedia is an independent fan project, not affiliated with the NBA or its teams. Data from stats.nba.com.",
  "{name} 的打法原型与超能力 · NBA {season}": "{name}: archetypes and superpowers · NBA {season}",
  "生涯视图：每名球员各赛季的打法按上场分钟加权平均，至少有一季满 500 分钟才算核心样本。":
    "Career view: each player's seasons averaged by minutes played; a player counts as a core sample with at least one 500-minute season.",
  "本赛季刚开始，还没有球员满 500 分钟：下面显示全部球员，位置和定位都是低置信度的参考。":
    "The season has just started and nobody has 500 minutes yet: everyone is shown, and positions and roles are low-confidence.",
  // teams
  "整体检验显示进攻体系和防守体系之间存在克制关系（p = {p}）；单格要看 ● 标记和误差，别过度解读。": "The overall test finds matchup structure between offensive and defensive systems (p = {p}); read single cells by their ● mark and error, and do not over-read them.",
  "结论：没有发现可靠的克制关系。{n} 场比赛里，各格的差别最多 {max} 分 / 场，和随机波动无法区分（整体检验 p = {p}）；风格对风格的优劣，远不如球队本身的强弱重要。": "Finding: no reliable matchup effect. Across {n} games no cell differs by more than {max} points per game, which cannot be told apart from chance (overall test p = {p}); style-on-style edges matter far less than how strong the teams are.",
  "{style} 进攻面对不同防守：每场得分比预期多 / 少": "{style} offence against each defence: points per game above / below expectation",
  "{tag} 面对不同进攻：对手得分比预期多 / 少（负 = 防守占优）": "{tag} against each offence: opponent points above / below expectation (negative = the defence has the edge)",
  "进攻角色搭配": "Offensive role pairings", "防守角色搭配": "Defensive role pairings", "进攻原型": "Offence archetype", "防守原型": "Defence archetype", "误差 ±{se}": "Error ±{se}",
  "两类进攻球员同时在场时，球队每 100 回合的进攻效率比「两人各自水平」预测的多（红）或少（蓝）几分。对角线是两个同类球员搭配。":
    "Points per 100 possessions a team's offence scores above (red) or below (blue) what the two players' own levels predict while these two kinds of offensive player share the floor. The diagonal is two players of the same kind.",
  "两类防守球员同时在场时，球队每 100 回合的防守效率（少丢分为好）比「两人各自水平」预测的好（红）或差（蓝）几分。对角线是两个同类球员搭配。":
    "Points per 100 possessions a team's defence saves (red) or concedes (blue) compared with what the two players' own levels predict while these two kinds of defender share the floor. The diagonal is two players of the same kind.",
  "● 表示效应超过 2 个标准误（按球队赛季重抽样）。基于 {n} 对队友组合、{poss} 个回合，各赛季 {from}–{to}。":
    "● marks an effect beyond 2 standard errors (resampling team-seasons). Based on {n} teammate pairs and {poss} possessions, seasons {from}–{to}.",
  "读法：效应很小，在没见过的球员对上加入它只让预测误差减少 {gain}%，所以这是倾向的描述，不能用来预测。":
    "How to read it: the effects are small, and adding them cuts held-out prediction error by only {gain}%, so this describes tendencies and cannot be used to predict.",
  "球员类型克制关系": "Player-type matchups",
  "每格是这类进攻球员面对这类防守球员时，每 100 个回合比「两人各自水平」预测的多（红）或少（蓝）几分，已剔除球员自身水平。数据是追踪数据里的对位回合（平均每 100 回合 {ppp} 分）。":
    "Each cell is how many points per 100 matchup possessions this kind of offensive player scores above (red) or below (blue) what the two players' own levels predict. Player talent is removed. Possessions come from tracked matchup data (average {ppp} points per 100).",
  "{n} 个赛季平均": "Average of {n} seasons", "进攻原型 ↓ / 防守原型 →": "Offence archetype ↓ / defence archetype →",
  "各赛季之间的标准差 ±{sd}": "Spread across seasons ±{sd}",
  "基于 {n} 个球员对位组合、{poss} 个回合。": "Based on {n} player pairs and {poss} possessions.", "整体检验 p = {p}。": "Overall test p = {p}.",
  "各赛季的表格之间平均相关 r = {r}，说明格局很稳定。": "The tables of different seasons correlate at r = {r} on average: the pattern is stable.",
  "读法：这是「谁守谁」的描述，不是因果上的克制。教练会让护框的人去守对方内线，数值会混有这种安排。我们用 9 个赛季回测过：把它加进球队强弱之上，并不能更好地预测比赛胜负，所以没有用在预测里。":
    "How to read it: this describes who guards whom, not a causal counter. Coaches send rim protectors to the other team's bigs, and the numbers carry that assignment. We backtested it over 9 seasons: added on top of team strength it does not predict game results better, so it is not used in predictions.",
  "进攻体系 ↓ / 防守体系 →": "Offence system ↓ / defence system →",
  "只有 {n} 支球队属于这个体系，结果更像这几支球队自己的特点。": "Only {n} team-seasons belong to this system, so the result reflects those teams' own habits.",
  "原始 {raw} 分，误差 ±{se}，{n} 场": "raw {raw} pts, ±{se}, {n} games",
  "每格是这类进攻在这类防守面前，每场比分比「两队自身水平」预测的多（红）或少（蓝）几分；已剔除球队强弱（球员水平、教练、节奏）和主场。● 表示效应超过 2 个标准误；数值已向 0 收缩，噪声大的格子收得更多。": "Each cell: points per game this kind of offence scores against this kind of defence above (red) or below (blue) what the two teams' own levels predict. Team strength (player talent, coaching, pace) and home court are removed. ● = effect beyond 2 standard errors; values are shrunk toward 0, more so where the data are noisy.",
  "基于 {seasons} 共 {n} 场常规赛；整体检验 p = {p}": "Based on {n} regular-season games in {seasons}; overall test p = {p}",
  "；前后两个赛季的格子相关 r = {r}": "; first vs last season cell correlation r = {r}",
  "；真实效应的标准差约 {tau} 分 / 场。": "; the true effects have an sd of about {tau} points per game.",
  "克制关系": "Matchups",
  "联盟第 {n}": "League rank {n}",
  "每百回合得分": "Points scored / 100",
  "节奏": "Pace",
  "相对当季联盟的特点（σ；黑色竖线是同体系球队的平均；# 是联盟排名）": "Traits vs that season's league (σ; the black tick is the average of teams in the same system; # is league rank)",
  "只看最突出的 8 项": "Show the 8 standout traits",
  "展开全部特征": "Show all traits",
  "这个赛季没有球队层面的打法数据。": "No team-level play data for this season.",
  "同体系的球队": "Teams in the same system",
  "轮换里哪一类防守球员最多：比联盟平均更突出的那一类决定了标签。": "Which kind of defender the rotation leans on most: the type that stands out most from the league average sets the label.",
  "每百回合失分": "Points allowed / 100",
  "轮换的防守构成（按分钟加权；黑色竖线是联盟平均；# 是联盟排名）": "Rotation's defensive makeup (minutes-weighted; the black tick is the league average; # is league rank)",
  "均值 {n}%": "avg {n}%",
  "同防守体系的球队": "Teams with the same defensive system",
  "联盟对比：进攻评分 × 防守评分": "League view: offense rating × defense rating",
  "每个点是一支球队，越靠右上两端越强；颜色是进攻体系，80 分是联盟平均。点击球队进入它的页面。": "Each dot is a team; the further up and right, the stronger on both ends. Colour is the offensive system; 80 is the league average. Click a team to open its page.",
  "体系分析": "System analysis",
  "伤停超过一个月：不计入球队的评分和阵容构成。": "Out for over a month: left out of the team's rating and rotation.",
  "球队评分里按 {pct}% 计算。": "Counts {pct}% toward the team rating.",
  "球队评分和阵容构成会考虑伤病：伤停超过一个月的球员（{names}）不计入，较短的缺阵按出战比例折算。": "Team ratings and rotation account for injuries: players out for over a month ({names}) are left out, shorter absences are discounted.",
  "、": ", ",
  "无": "none",
  "复出时间未定": "Return date not set",
  "主": "H",
  "客": "A",
  "没有这支球队": "No such team",
  "{team} {season} 阵容、评分与赛程": "{team} {season}: roster, ratings and schedule",
  "球员阵容与数据": "Roster and stats",
  "本赛季为这支球队打过球的球员，按上场时间排序；场均数据是他在这支球队的常规赛场均。": "Everyone who played for this team this season, by minutes; per-game numbers are his regular-season averages with the team.",
  "已离队": "Traded away",
  "打法": "Style",
  "未来赛程": "Upcoming games",
  "已打比赛": "Played games",
  "还没有打过比赛。": "No games played yet.",
  "← 全部球队体系": "← All team systems",
  "主场": "Home",
  "客场": "Away",
  "进攻体系": "Offensive system", "球队体系": "Team Systems", "防守体系": "Defensive system", "4 种防守体系的特征": "What defines the 4 defensive systems",
  "每格是这一类防守球员的平均值，单位是相对联盟球员的标准差（σ）：红色高于联盟，蓝色低于联盟。球队的防守体系由轮换球员的这些类型按分钟加权得出。点列名筛选球队。":
    "Each cell is the average of players of this defensive type, in standard deviations (σ) from the league's players: red is above the league, blue below. A team's defensive system comes from its rotation's types weighted by minutes. Click a column to filter teams.",
  "体型": "Build", "护框与篮板": "Rim and rebounding", "抢断与活动量": "Steals and activity", "防守的战术类型占比": "Share of play types defended",
  "防守体系看的是球队的轮换更依赖哪一种防守方式。每名球员的防守特征（抢断、干扰、护框次数、封盖、造犯规、对位三分和近筐出手占比、防守速度等）先归成 4 种防守原型，每人是这几种原型的混合。":
    "A team's defensive system is the kind of defense its rotation leans on most. Each player's defensive traits (steals, deflections, rim contests, blocks, charges drawn, share of threes and rim shots defended, defensive speed) are grouped into 4 defensive archetypes, and every player is a mix of them.",
  "球队的防守构成是轮换 9 人的防守原型按分钟加权，再和当季联盟比；标签取这支球队比联盟平均更突出的那一种。它是「最偏向」，不是球队唯一的防守方式，也不是聚类分出来的派系。":
    "A team's defensive makeup is its 9-man rotation's defensive archetypes weighted by minutes and compared with that season's league; the label is the one the team stands out on most. It means \"leans most toward\", not the team's only way to defend, and it is not a cluster.",
  "轮换里护框、封盖多，保护内线。": "Lots of rim protection and blocks in the rotation; protects the paint.",
  "抢断、干扰多，靠主动出击制造失误。": "Lots of steals and deflections; forces turnovers by attacking.",
  "防外线投手，封盖三分出手。": "Guards shooters on the perimeter and contests threes.",
  "防守速度快、对位多，常被对手针对。": "Fast on defense and chases a lot; opponents often target them.",
  "球队评分里的「防守」一半来自轮换球员的防守评分，一半来自球队实际的每百回合失分。": "The defense rating is half the rotation's defensive ratings and half the team's actual points allowed per 100 possessions.",
  "总评": "Overall", "分区": "Division", "战绩排名": "Standings",
  "大西洋": "Atlantic", "中部": "Central", "东南": "Southeast", "西北": "Northwest", "太平洋": "Pacific", "西南": "Southwest",
  "{season} 赛季每支球队怎么打：进攻体系、球队评分和主力轮换。": "How every team plays in {season}: offensive system, team ratings and rotation.",
  "进攻特点（相对当季联盟）": "Offensive traits (vs league that season)", "球员构成": "Player makeup",
  "5 种进攻体系的特征": "What defines the 5 offensive systems", "特征": "Feature",
  "战术类型占比": "Play-type mix", "传球与触球": "Passing and touches", "出手与节奏": "Shots and pace",
  "每格是这一类球队的平均值，单位是相对当季联盟的标准差（σ）：红色高于联盟，蓝色低于联盟。点列名筛选球队。":
    "Each cell is the style's average, in standard deviations from that season's league (σ): red is above the league, blue below. Click a column name to filter teams.",
  "大量弧顶三分和急停跳投，持球单打多；禁区得分和空切少。": "Lots of above-the-break and pull-up threes and isolation; few paint points or cuts.",
  "空切、绕掩护和接球投篮多；传球多、持球时间短，大部分进球有助攻。": "Cuts, off-screen action and catch-and-shoot; many passes, short touches, most baskets assisted.",
  "进攻经由低位和肘区展开：背身、手递手和中距离多，三分少，节奏偏慢。": "Offense runs through the post and elbows: post-ups, handoffs and midrange, fewer threes, slower pace.",
  "突破多、节奏快，转换进攻和篮下出手多，外线配定点投篮；中距离和急停少。": "Drives and pace: transition and rim attempts with spot-up shooters; little midrange or pull-up shooting.",
  "挡拆持球为主，每次触球时间长、运球多，急停中投多；传球和接球投篮少。": "Ball-screen heavy: long touches, many dribbles and pull-up midrange; few passes or catch-and-shoot looks.",
  "进攻体系看的是球队怎么打：战术类型占比（挡拆、单打、空切、背身……）、传球和触球、突破、出手分布和节奏，都和当季联盟比，再用 2015-16 以来的全部球队聚成 5 类。打法是连续的，归类表示「最接近」，不是严格的派系。":
    "Offensive systems describe how a team plays: play-type mix (pick-and-roll, isolation, cuts, post-ups…), passing and touches, drives, shot locations and pace, each against that season's league, clustered into 5 systems using every team since 2015-16. Systems are a continuum; a label means closest to, not a strict camp.",
  "「球员构成」是轮换 9 人的打法原型按分钟加权。": "Player makeup is the rotation's 9 players' archetypes, weighted by minutes.", "轮换 OVR": "Rotation OVR",
  // offense / defense ratings
  "综合": "Overall", "进攻评分": "Offense rating",
  "赛季初过渡值：定位、超能力和评分按本赛季 {w} + {prior} 赛季 {pw} 合成，本赛季打得越多，占比越高。":
    "Early-season transition values: roles, superpowers and ratings blend this season {w} with {prior} {pw}; this season's share grows as he plays.",
  "过渡值 = {w} × 本赛季 {own} + {pw} × {prior} 赛季 {p}": "Transition value = {w} × this season {own} + {pw} × {prior} {p}",
  "进行中的赛季：本赛季权重 = 分钟 ÷（分钟 + 600），其余来自上赛季。约 5 场首发（170 分钟）时本赛季占 22%，600 分钟占一半，1800 分钟占 75%。新秀没有上赛季，样本少时向替补水平靠拢。":
    "Season in progress: this season's weight = minutes ÷ (minutes + 600), the rest comes from last season. About 5 starts (170 minutes) gives this season 22%, 600 minutes half, 1,800 minutes 75%. Rookies have no last season, so small samples lean toward bench level.",
  "赛季初过渡值：进攻体系和球队评分按场次把本赛季和上赛季合成（本赛季权重 = 场次 ÷（场次 + 20）），轮换和风格还会变化。":
    "Early-season transition values: offensive systems and team ratings blend this season with last by games played (this season's weight = games ÷ (games + 20)); rotations and styles will still shift.",
  "本赛季刚开始，还没有球员满 500 分钟：下面显示全部球员。定位是本赛季和上赛季的过渡值，图上的位置只用本赛季数据，可信度低。":
    "The season has just started and no one has 500 minutes yet, so every player is shown. Roles are transition values blending this season with last; map positions use this season only and are low confidence.",
  "数字的颜色是 2K 式卡牌等级：铜（70 以下）、银（70+）、金（80+）、紫晶（87+）、钻石（92+）、银河蛋白石（96+）。":
    "Number colours follow 2K-style card tiers: bronze (under 70), silver (70+), gold (80+), amethyst (87+), diamond (92+), galaxy opal (96+).", "防守评分": "Defense rating", "评分类型": "Rating type",
  "攻": "OFF", "守": "DEF", "组织": "Playmaking", "进攻篮板": "Offensive rebounding", "在场进攻": "On-court offense",
  "防守篮板": "Defensive rebounding", "在场防守": "On-court defense",
  "助攻率 {ast}，失误率 {tov}": "Assist rate {ast}, turnover ratio {tov}", "进攻篮板率 {v}": "Offensive rebound rate {v}",
  "防守篮板率 {v}": "Defensive rebound rate {v}", "每 36 分钟 {v} 次": "{v} per 36 minutes",
  "他在场时球队每 100 回合得 {on} 分（联盟 {lg}）": "With him on the floor the team scores {on} per 100 possessions (league {lg})",
  "他在场时球队每 100 回合失 {on} 分（联盟 {lg}）": "With him on the floor the team allows {on} per 100 possessions (league {lg})",
  "各赛季{k}评分": "{k} rating by season", "{k}巅峰 {p}，生涯 {c}": "{k} peak {p}, career {c}",
  "进攻评分：得分效率与量 45%、组织（助攻率减一半失误率）25%、进攻篮板 10%、在场进攻 20%。":
    "Offense rating: scoring efficiency and volume 45%, playmaking (assist rate minus half the turnover ratio) 25%, offensive rebounding 10%, on-court offense 20%.",
  "防守评分：抢断 20%、盖帽 15%、防守篮板 15%、在场防守 50%。在场数据和他自己球队比（再加三成球队整体水平），所以防守好的球队不会把每个人都抬高。":
    "Defense rating: steals 20%, blocks 15%, defensive rebounding 15%, on-court defense 50%. On-court numbers are compared with his own team (plus 30% of the team's overall level), so a great defensive team doesn't lift everyone on it.",
  "换算成 2K 式分数：77 + 6.5 × σ，范围 40–99。联盟中位数约 75，前 10% 约 82 以上，最顶尖接近 99。三项评分各自独立计算，综合评分不是攻守的平均。":
    "Converted to a 2K-style score: 77 + 6.5 × σ, range 40–99. The league median is about 75, the top 10% above about 82, the very best near 99. The three ratings are computed separately; overall is not the average of offense and defense.",
  "这是第一版（只用 box score）。它偏爱篮板多、出手效率高的内线；防守尤其难从 box score 看出来，换防、协防和限制投篮都看不到。之后会换成考虑队友和对手的影响力模型（RAPM）。每个赛季都在当季内排名，所以不同年代可以直接比较。":
    "This is version 1 (box score only). It favours efficient, rebounding bigs, and defense is especially hard to see in a box score: switching, help defense and shot deterrence don't show up. It will be replaced by an impact model (RAPM) that accounts for teammates and opponents. Every season is ranked within itself, so eras can be compared directly.",
  "球队评分": "Team rating", "每 100 回合得分 / 失分": "Points scored / allowed per 100 possessions",
  "得 {o} · 失 {d} / 百回合": "{o} for · {d} against / 100",
  "球队评分（综合、进攻、防守）一半来自轮换球员的评分（按分钟加权），一半来自球队实际的每百回合净胜分、得分和失分，各自在当季 30 队里排名，80 分是联盟平均。":
    "Team ratings (overall, offense, defense) are half the rotation's player ratings (minutes-weighted) and half the team's actual net rating, points scored and points allowed per 100 possessions, each ranked among that season's 30 teams; 80 is league average.",
  "主力轮换": "Main rotation", "{n} 支球队": "{n} teams",
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
  "突破分球": "Drive and Kick", "外线单打": "Perimeter Iso", "跑动传切": "Motion Offense",
  "冲击转换": "Drive and Run", "持球挡拆": "Ball-screen Creator", "护框型防守": "Rim-protection defense", "侵略型防守": "Disruptive defense",
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
  // The URL is the source of truth: ?lang=en is the English page (what gets shared and indexed),
  // no param is Chinese. Whatever navigation drops the param is put back below.
  const location = useLocation();
  const navigate = useNavigate();
  const [lang, setLangState] = useState<Lang>(() =>
    new URLSearchParams(window.location.search).get("lang") === "en" ? "en" : "zh");
  const setLang = useCallback((l: Lang) => setLangState(l), []);
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if ((params.get("lang") === "en") === (lang === "en") && (lang === "en" || !params.has("lang"))) return;
    if (lang === "en") params.set("lang", "en"); else params.delete("lang");
    const search = params.toString();
    navigate({ pathname: location.pathname, search: search ? `?${search}` : "", hash: location.hash }, { replace: true, state: location.state });
  }, [lang, location, navigate]);
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

const SITE_TITLE = { zh: "Hoopedia · NBA 球员图鉴：打法原型、超能力与数据", en: "Hoopedia · NBA Player Encyclopedia: archetypes, superpowers and stats" };

/** Sets the browser tab / search title: "<page> · Hoopedia", or the site title on its own. */
export function usePageTitle(title?: string) {
  const { lang } = useLang();
  useEffect(() => {
    document.title = title ? `${title} · Hoopedia` : SITE_TITLE[lang];
  }, [title, lang]);
}

export function useLang(): LangCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLang outside LangProvider");
  return ctx;
}
