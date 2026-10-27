import { useState } from "react";
import { seriesColor, useRoleMatchups } from "../api";
import { useLang } from "../i18n";
import { shade, signed } from "../teamFeatures";

const POOLED = "all";
const FULL = 35;   // effect (points per 100 partial possessions) shown at full colour

/** Offensive archetype x defensive archetype: points per 100 partial possessions above what the two
 *  players' own levels predict (player_matchup.py). `pickOff` / `pickDef` highlight a row or column. */
export default function RoleMatchup({ pickOff, pickDef }: { pickOff: number | null; pickDef: number | null }) {
  const { t, name } = useLang();
  const q = useRoleMatchups();
  const [season, setSeason] = useState(POOLED);
  const { cells, meta, offense, defense } = q.data ?? { cells: [], meta: [], offense: [], defense: [] };
  if (!meta.length) return null;
  const pooled = meta.find((m) => m.season === POOLED);
  const cur = meta.find((m) => m.season === season) ?? pooled!;
  const cell = (o: number, d: number) => cells.find((c) => c.season === season && c.off_type === o && c.def_type === d);
  return (
    <section className="panel">
      <span className="caption">{t("球员类型克制关系")}</span>
      <p className="note" style={{ margin: "8px 0" }}>
        {t("每格是这类进攻球员面对这类防守球员时，每 100 个回合比「两人各自水平」预测的多（红）或少（蓝）几分，已剔除球员自身水平。数据是追踪数据里的对位回合（平均每 100 回合 {ppp} 分）。",
          { ppp: cur.mean_ppp.toFixed(0) })}
      </p>
      <div className="row" style={{ marginBottom: 10 }}>
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("赛季")}
          <select className="select" value={season} onChange={(e) => setSeason(e.target.value)}>
            <option value={POOLED}>{t("{n} 个赛季平均", { n: meta.length - 1 })}</option>
            {meta.filter((m) => m.season !== POOLED).map((m) => <option key={m.season} value={m.season}>{m.season}</option>)}
          </select>
        </label>
      </div>
      <div className="table-box">
        <table className="data" style={{ minWidth: 480 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>{t("进攻原型 ↓ / 防守原型 →")}</th>
              {defense.map((d) => (
                <th key={d.type_id} className="num-col" style={d.type_id === pickDef ? { textDecoration: "underline" } : undefined}>
                  <span className="swatch" style={{ background: seriesColor(d.type_id) }} /> {name(d.name ?? "")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {offense.map((o) => (
              <tr key={o.type_id} style={{ opacity: pickOff == null || pickOff === o.type_id ? 1 : 0.45 }}>
                <td style={{ fontWeight: o.type_id === pickOff ? 700 : 400 }}>
                  <span className="swatch" style={{ background: seriesColor(o.type_id) }} /> {name(o.name ?? "")}
                </td>
                {defense.map((d) => {
                  const c = cell(o.type_id, d.type_id);
                  if (!c) return <td key={d.type_id} className="num-col">—</td>;
                  return (
                    <td key={d.type_id} className="num-col"
                      style={{ background: shade(c.effect, FULL), color: Math.abs(c.effect) > FULL * 0.8 ? "#fff" : undefined,
                        fontVariantNumeric: "tabular-nums", outline: o.type_id === pickOff && d.type_id === pickDef ? "3px solid var(--ink)" : undefined }}
                      title={c.spread != null ? t("各赛季之间的标准差 ±{sd}", { sd: c.spread.toFixed(1) }) : undefined}>
                      {signed(c.effect, 0)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ margin: "8px 0 0" }}>
        {t("基于 {n} 个球员对位组合、{poss} 个回合。", { n: cur.n_pairs.toLocaleString(), poss: cur.n_poss.toLocaleString() })}{" "}
        {cur.p_value != null && t("整体检验 p = {p}。", { p: cur.p_value.toFixed(2) })}
        {pooled?.season_corr != null && season === POOLED && t("各赛季的表格之间平均相关 r = {r}，说明格局很稳定。", { r: pooled.season_corr.toFixed(2) })}
      </p>
      <p className="note" style={{ margin: "6px 0 0" }}>
        {t("读法：这是「谁守谁」的描述，不是因果上的克制。教练会让护框的人去守对方内线，数值会混有这种安排。我们用 9 个赛季回测过：把它加进球队强弱之上，并不能更好地预测比赛胜负，所以没有用在预测里。")}
      </p>
    </section>
  );
}
