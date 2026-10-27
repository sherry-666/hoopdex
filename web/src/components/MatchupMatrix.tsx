import { useMatchups } from "../api";
import { useLang } from "../i18n";
import { DEFENSE_TAGS, shade, signed } from "../teamFeatures";

const DEFENSE_ORDER = Object.values(DEFENSE_TAGS);
const FEW_TEAMS = 6;   // an offensive system seen in fewer team-seasons than this is one team's habits

/** Offence system x defence system: points per game the offence scores above what the two teams' own levels predict. */
export default function MatchupMatrix({ offStyle, defTag }: { offStyle?: number; defTag?: string }) {
  const { t, name } = useLang();
  const q = useMatchups();
  const { cells, styles, meta } = q.data ?? { cells: [], styles: [], meta: null };
  if (!meta) return null;
  const cell = (o: number, d: string) => cells.find((c) => c.off_style === o && c.def_tag === d);
  const defs = DEFENSE_ORDER.filter((d) => cells.some((c) => c.def_tag === d));
  const biggest = Math.max(...cells.map((c) => Math.abs(c.raw_effect)));
  return (
    <div>
      <p className="bubble" style={{ "--bubble-edge": meta.p_value < 0.05 ? "var(--pop-yellow)" : "var(--ink)", margin: "0 0 18px" } as React.CSSProperties}>
        {meta.p_value < 0.05
          ? t("整体检验显示进攻体系和防守体系之间存在克制关系（p = {p}）；单格要看 ● 标记和误差，别过度解读。", { p: meta.p_value.toFixed(2) })
          : t("结论：没有发现可靠的克制关系。{n} 场比赛里，各格的差别最多 {max} 分 / 场，和随机波动无法区分（整体检验 p = {p}）；风格对风格的优劣，远不如球队本身的强弱重要。", { n: meta.n_games.toLocaleString(), max: biggest.toFixed(1), p: meta.p_value.toFixed(2) })}
      </p>
      <div className="table-box">
        <table className="data" style={{ minWidth: 520 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>{t("进攻体系 ↓ / 防守体系 →")}</th>
              {defs.map((d) => <th key={d} className="num-col" style={d === defTag ? { textDecoration: "underline" } : undefined}>{name(d)}</th>)}
            </tr>
          </thead>
          <tbody>
            {styles.map((s) => {
              const few = (cells.find((c) => c.off_style === s.style_id)?.off_teams ?? 0) < FEW_TEAMS;
              return (
                <tr key={s.style_id} style={{ opacity: offStyle == null || offStyle === s.style_id ? 1 : 0.45 }}>
                  <td style={{ fontWeight: s.style_id === offStyle ? 700 : 400 }}>
                    {name(s.name ?? "")}
                    {few && <span className="note" title={t("只有 {n} 支球队属于这个体系，结果更像这几支球队自己的特点。", { n: cells.find((c) => c.off_style === s.style_id)?.off_teams ?? 0 })}> ⚠</span>}
                  </td>
                  {defs.map((d) => {
                    const c = cell(s.style_id, d);
                    if (!c) return <td key={d} className="num-col">—</td>;
                    const z = c.raw_effect / c.se;
                    return (
                      <td key={d} className="num-col" style={{ background: shade(c.effect, 1.6), color: Math.abs(c.effect) > 1.3 ? "#fff" : undefined,
                        fontWeight: Math.abs(z) >= 2 ? 800 : 400, outline: d === defTag && s.style_id === offStyle ? "3px solid var(--ink)" : undefined,
                        fontVariantNumeric: "tabular-nums" }}
                        title={t("原始 {raw} 分，误差 ±{se}，{n} 场", { raw: signed(c.raw_effect), se: c.se.toFixed(1), n: c.n })}>
                        {signed(c.effect)}{Math.abs(z) >= 2 ? " ●" : ""}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ margin: "8px 0 0" }}>
        {t("每格是这类进攻在这类防守面前，每场比分比「两队自身水平」预测的多（红）或少（蓝）几分；已剔除球队强弱（球员水平、教练、节奏）和主场。● 表示效应超过 2 个标准误；数值已向 0 收缩，噪声大的格子收得更多。")}{" "}
        {t("基于 {seasons} 共 {n} 场常规赛；整体检验 p = {p}", { seasons: meta.seasons.join("、"), n: meta.n_games, p: meta.p_value.toFixed(2) })}
        {meta.season_corr != null && t("；前后两个赛季的格子相关 r = {r}", { r: meta.season_corr.toFixed(2) })}
        {t("；真实效应的标准差约 {tau} 分 / 场。", { tau: meta.tau.toFixed(1) })}
      </p>
    </div>
  );
}
