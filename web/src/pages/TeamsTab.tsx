import { useState } from "react";
import { Link } from "react-router-dom";
import { seriesColor, TeamProfile, useTeams } from "../api";
import { Failed, Loading, MixBar } from "../components/comic";
import { OffDef, OvrBadge } from "../components/rating";
import { useLang } from "../i18n";
import { teamName } from "../teams";
import { FEATURE_GROUPS, signature, teamFeature } from "../teamFeatures";
import type { TeamStyle } from "../api";

/** Each style's average on every feature, in sd from that season's league. */
function StyleTable({ styles, pick, onPick }: { styles: TeamStyle[]; pick: number | null; onPick: (id: number | null) => void }) {
  const { t, name, lang } = useLang();
  const shade = (z: number) => {
    const a = Math.round(Math.min(1, Math.abs(z) / 1.6) * 85);
    return `color-mix(in srgb, var(${z >= 0 ? "--seq-hi" : "--seq-lo"}) ${a}%, var(--panel))`;
  };
  return (
    <details className="panel" style={{ padding: "10px 14px" }}>
      <summary style={{ cursor: "pointer", fontFamily: "var(--font-display)", fontSize: 18 }}>{t("5 种进攻体系的特征")}</summary>
      <p className="note" style={{ margin: "8px 0" }}>{t("每格是这一类球队的平均值，单位是相对当季联盟的标准差（σ）：红色高于联盟，蓝色低于联盟。点列名筛选球队。")}</p>
      <div className="table-box">
        <table className="data" style={{ minWidth: 560 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>{t("特征")}</th>
              {styles.map((s) => (
                <th key={s.style_id} className="num-col" style={{ cursor: "pointer", textDecoration: pick === s.style_id ? "underline" : undefined }}
                  onClick={() => onPick(pick === s.style_id ? null : s.style_id)}>{name(s.name)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURE_GROUPS.map(([group, codes]) => [
              <tr key={group}><td colSpan={styles.length + 1} style={{ fontWeight: 700, paddingTop: 10 }}>{t(group)}</td></tr>,
              ...codes.filter((c) => c in (styles[0]?.centroid ?? {})).map((c) => (
                <tr key={c}>
                  <td>{teamFeature(c, lang)}</td>
                  {styles.map((s) => {
                    const z = s.centroid[c] ?? 0;
                    return (
                      <td key={s.style_id} className="num-col" style={{ background: shade(z), opacity: pick == null || pick === s.style_id ? 1 : 0.35,
                        color: Math.abs(z) > 1.1 ? "#fff" : undefined, fontVariantNumeric: "tabular-nums" }}>
                        {z > 0 ? "+" : z < 0 ? "−" : ""}{Math.abs(z).toFixed(1)}
                      </td>
                    );
                  })}
                </tr>
              )),
            ])}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function mixFrom(shares: Record<string, number>, order: string[]) {
  return order.map((name, id) => ({ id, name, weight: shares[name] ?? 0 }));
}

function TeamCard({ t, season, archetypes }: { t: TeamProfile; season: string; archetypes: { offense: string[]; defense: string[] } }) {
  const { t: tr, name, lang } = useLang();
  const off = mixFrom(t.off_mix, archetypes.offense);
  const top = [...off].sort((a, b) => b.weight - a.weight).slice(0, 3);
  return (
    <article className="panel pop-in" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
        <div style={{ minWidth: 0 }}>
          <h3 style={{ fontSize: 24, lineHeight: 1.1 }}>{teamName(t.team, lang, lang === "en")}</h3>
          <span className="tag" style={{ marginTop: 6 }}>{name(t.defense_tag)}</span>
        </div>
        <div style={{ textAlign: "center", display: "grid", justifyItems: "center", gap: 4 }}>
          <OvrBadge ovr={t.ovr} size={52} />
          <div className="note">{tr("球队评分")}</div>
        </div>
      </div>
      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <OffDef off={t.off} def={t.def} size={16} />
        {t.ortg != null && t.drtg != null && (
          <span className="note" title={tr("每 100 回合得分 / 失分")}>
            {tr("得 {o} · 失 {d} / 百回合", { o: t.ortg.toFixed(1), d: t.drtg.toFixed(1) })}
          </span>
        )}
      </div>
      {t.system && (
        <div>
          <div className="note" style={{ marginBottom: 4 }}>{tr("进攻特点（相对当季联盟）")}</div>
          <div className="row" style={{ gap: 6 }}>
            {signature(t.system).map(([code, z]) => (
              <span key={code} className="tag" style={z > 0 ? { background: "var(--pop-yellow)", color: "var(--on-yellow)" } : undefined}>
                {teamFeature(code, lang)} {z > 0 ? "↑" : "↓"} {Math.abs(z).toFixed(1)}σ
              </span>
            ))}
          </div>
        </div>
      )}
      <div>
        <div className="note">{tr("球员构成")}</div>
        <MixBar mix={off} height={16} />
        <div className="row" style={{ gap: 10, marginTop: 4 }}>
          {top.map((m) => (
            <span key={m.id} className="row" style={{ gap: 4, fontSize: "var(--size-caption)" }}>
              <span className="swatch" style={{ background: seriesColor(m.id) }} />{name(m.name)} {Math.round(m.weight * 100)}%
            </span>
          ))}
        </div>
      </div>
      <div>
        <div className="note">{tr("防守")}</div>
        <MixBar mix={mixFrom(t.def_mix, archetypes.defense)} height={12} />
      </div>
      <div>
        <div className="note" style={{ marginBottom: 4 }}>{tr("主力轮换")}</div>
        <ol style={{ margin: 0, paddingLeft: "1.2em", display: "grid", gap: 2 }}>
          {t.core.slice(0, 6).map((p) => (
            <li key={p.player_id} style={{ fontSize: "var(--size-caption)" }}>
              <Link to={`/players/${p.player_id}?season=${season}`}>{p.name}</Link>
              {p.ovr != null && <b> {p.ovr}</b>}
              {p.off != null && p.def != null && <span className="note"> ({tr("攻")}{p.off}/{tr("守")}{p.def})</span>}
              {p.style && <span className="note"> · {name(p.style)}</span>}
            </li>
          ))}
        </ol>
      </div>
    </article>
  );
}

export default function TeamsTab({ season, early }: { season: string | undefined; early: boolean }) {
  const { t, name } = useLang();
  const view = useTeams(season);
  const [style, setStyle] = useState<number | null>(null);
  if (view.isLoading || !season) return <Loading what="数据" />;
  if (view.error || !view.data) return <Failed error={view.error} />;
  const { styles, teams, archetypes } = view.data;
  const shown = styles.filter((s) => style == null || s.style_id === style);
  return (
    <>
      <p className="note" style={{ maxWidth: "80ch", margin: 0 }}>
        {t("进攻体系看的是球队怎么打：战术类型占比（挡拆、单打、空切、背身……）、传球和触球、突破、出手分布和节奏，都和当季联盟比，再用 2015-16 以来的全部球队聚成 5 类。打法是连续的，归类表示「最接近」，不是严格的派系。")}{" "}
        {t("「球员构成」是轮换 9 人的打法原型按分钟加权。")}{" "}
        {t("交易过的球员算在他最后效力的球队。")}{" "}
        {t("球队评分（综合、进攻、防守）一半来自轮换球员的评分（按分钟加权），一半来自球队实际的每百回合净胜分、得分和失分，各自在当季 30 队里排名，80 分是联盟平均。")}
      </p>
      {early && <p className="bubble" style={{ margin: 0 }}>{t("本赛季刚开始，轮换和风格还会变化。")}</p>}
      <div className="row">
        <button type="button" className="chip" aria-pressed={style === null} onClick={() => setStyle(null)}>{t("全部")}</button>
        {styles.map((s) => (
          <button key={s.style_id} type="button" className="chip" aria-pressed={style === s.style_id}
            onClick={() => setStyle(style === s.style_id ? null : s.style_id)}>
            {name(s.name)} <span style={{ color: "var(--muted)" }}>{teams.filter((tm) => tm.style_id === s.style_id).length}</span>
          </button>
        ))}
      </div>
      <StyleTable styles={styles} pick={style} onPick={setStyle} />
      {shown.map((s) => {
        const members = teams.filter((tm) => tm.style_id === s.style_id);
        if (!members.length) return null;
        return (
          <section key={s.style_id} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <span className="caption" style={{ fontSize: 20 }}>{name(s.name)}</span>
              <span className="note" style={{ marginLeft: 10 }}>{t("{n} 支球队", { n: members.length })}</span>
              {s.description && <p style={{ margin: "8px 0 0", maxWidth: "70ch" }}>{t(s.description)}</p>}
            </div>
            <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 270px), 1fr))" }}>
              {members.map((tm) => <TeamCard key={tm.team} t={tm} season={season} archetypes={archetypes} />)}
            </div>
          </section>
        );
      })}
    </>
  );
}
