import { seriesColor, Side, useRoleSynergy } from "../api";
import { useLang } from "../i18n";
import { shade, signed } from "../teamFeatures";

const FULL = 3;   // net rating points per 100 possessions shown at full colour

/** Role x role on one side: how a team's offence (or defence) rates while two such teammates share the floor,
 *  above what their own levels predict (lineup_synergy.py). A symmetric table; `pick` highlights one role's row and column. */
export default function RoleSynergy({ side, pick }: { side: Side; pick: number | null }) {
  const { t, name } = useLang();
  const q = useRoleSynergy(side);
  const { cells, meta, types } = q.data ?? { cells: [], meta: null, types: [] };
  if (!meta) return null;
  const cell = (a: number, b: number) => cells.find((c) => c.type_a === Math.min(a, b) && c.type_b === Math.max(a, b));
  const lit = (id: number) => pick == null || pick === id;
  return (
    <section className="panel">
      <span className="caption">{t(side === "offense" ? "进攻角色搭配" : "防守角色搭配")}</span>
      <p className="note" style={{ margin: "8px 0" }}>
        {t(side === "offense"
          ? "两类进攻球员同时在场时，球队每 100 回合的进攻效率比「两人各自水平」预测的多（红）或少（蓝）几分。对角线是两个同类球员搭配。"
          : "两类防守球员同时在场时，球队每 100 回合的防守效率（少丢分为好）比「两人各自水平」预测的好（红）或差（蓝）几分。对角线是两个同类球员搭配。")}
      </p>
      <div className="table-box">
        <table className="data" style={{ minWidth: 560 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>{t(side === "offense" ? "进攻原型" : "防守原型")}</th>
              {types.map((o) => (
                <th key={o.type_id} className="num-col" style={o.type_id === pick ? { textDecoration: "underline" } : undefined}>
                  <span className="swatch" style={{ background: seriesColor(o.type_id) }} /> {name(o.name ?? "")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {types.map((r) => (
              <tr key={r.type_id}>
                <td style={{ fontWeight: r.type_id === pick ? 700 : 400 }}>
                  <span className="swatch" style={{ background: seriesColor(r.type_id) }} /> {name(r.name ?? "")}
                </td>
                {types.map((c) => {
                  const e = cell(r.type_id, c.type_id);
                  if (!e) return <td key={c.type_id} className="num-col">—</td>;
                  const sure = Math.abs(e.effect / e.se) >= 2;
                  return (
                    <td key={c.type_id} className="num-col"
                      style={{ background: shade(e.effect, FULL), color: Math.abs(e.effect) > FULL * 0.8 ? "#fff" : undefined,
                        fontWeight: sure ? 800 : 400, fontVariantNumeric: "tabular-nums", opacity: lit(r.type_id) || lit(c.type_id) ? 1 : 0.4 }}
                      title={t("误差 ±{se}", { se: e.se.toFixed(1) })}>
                      {signed(e.effect)}{sure ? " ●" : ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ margin: "8px 0 0" }}>
        {t("● 表示效应超过 2 个标准误（按球队赛季重抽样）。基于 {n} 对队友组合、{poss} 个回合，各赛季 {from}–{to}。",
          { n: meta.n_pairs.toLocaleString(), poss: meta.n_poss.toLocaleString(), from: meta.seasons[0], to: meta.seasons[meta.seasons.length - 1] })}
      </p>
      <p className="note" style={{ margin: "6px 0 0" }}>
        {t("读法：效应很小，在没见过的球员对上加入它只让预测误差减少 {gain}%，所以这是倾向的描述，不能用来预测。",
          { gain: Math.max(meta.cv_gain * 100, 0).toFixed(1) })}
      </p>
    </section>
  );
}
