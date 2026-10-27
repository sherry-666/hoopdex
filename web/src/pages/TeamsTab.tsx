import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { seriesColor, TeamProfile, useRankings, useTeams } from "../api";
import { Failed, Loading, MixBar, TeamLogo } from "../components/comic";
import { OffDef, OvrBadge } from "../components/rating";
import { useLang } from "../i18n";
import { DIVISIONS, divisionOf, teamName } from "../teams";
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
    <section style={{ marginTop: 16 }}>
      <h3 style={{ fontFamily: "var(--font-display)", fontSize: 18 }}>{t("5 种进攻体系的特征")}</h3>
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
    </section>
  );
}

function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="modal" onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
        <h2 style={{ fontSize: 24 }}>{title}</h2>
        <button type="button" className="chip" onClick={onClose} aria-label="×">×</button>
      </div>
      {open && <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 10 }}>{children}</div>}
    </dialog>
  );
}

function InfoButton({ label, onClick }: { label: string; onClick: () => void }) {
  return <button type="button" className="info-btn" aria-label={label} title={label} onClick={onClick}>!</button>;
}

function mixFrom(shares: Record<string, number>, order: string[]) {
  return order.map((name, id) => ({ id, name, weight: shares[name] ?? 0 }));
}

function TeamCard({ t, season, archetypes, style, rank }: { t: TeamProfile; season: string; archetypes: { offense: string[]; defense: string[] }; style?: TeamStyle; rank?: number }) {
  const { t: tr, name, lang } = useLang();
  const off = mixFrom(t.off_mix, archetypes.offense);
  const top = [...off].sort((a, b) => b.weight - a.weight).slice(0, 3);
  return (
    <article className="panel pop-in" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
        <div style={{ minWidth: 0 }}>
          <h3 style={{ fontSize: 24, lineHeight: 1.1 }}><TeamLogo team={t.team} size={40} />{teamName(t.team, lang, lang === "en")}</h3>
          <div className="row" style={{ gap: 6, marginTop: 6 }}>
            {style && <span className="tag" style={{ background: "var(--pop-yellow)", color: "var(--on-yellow)" }} title={tr("进攻体系")}>{tr("攻")} · {name(style.name)}</span>}
            <span className="tag" title={tr("防守体系")}>{tr("守")} · {name(t.defense_tag)}</span>
            {rank != null && <span className="tag" title={tr("战绩排名")}>#{rank}</span>}
          </div>
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

type SortKey = "ovr" | "off" | "def" | "division" | "rank";
const SORTS: Record<SortKey, string> = { ovr: "总评", off: "进攻", def: "防守", division: "分区", rank: "战绩排名" };

export default function TeamsTab({ season, early }: { season: string | undefined; early: boolean }) {
  const { t, name, lang } = useLang();
  const view = useTeams(season);
  const standings = useRankings(season);
  const [off, setOff] = useState<number | null>(null);
  const [def, setDef] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>("ovr");
  const [info, setInfo] = useState<"off" | "def" | null>(null);
  // Conference standing (1 = best) per team, when the season has standings.
  const rank = useMemo(() => {
    const m = new Map<string, number>();
    const d = standings.data;
    if (d) [...d.east, ...d.west].forEach((s) => m.set(s.team, s.rank));
    return m;
  }, [standings.data]);
  const conf = useMemo(() => {
    const m = new Map<string, number>();
    const d = standings.data;
    if (d) { d.east.forEach((s) => m.set(s.team, 0)); d.west.forEach((s) => m.set(s.team, 1)); }
    return m;
  }, [standings.data]);
  if (view.isLoading || !season) return <Loading what="数据" />;
  if (view.error || !view.data) return <Failed error={view.error} />;
  const { styles, teams, archetypes } = view.data;
  const styleOf = new Map(styles.map((s) => [s.style_id, s]));
  const defTags = [...new Set(teams.map((tm) => tm.defense_tag))];
  const byOvr = (a: TeamProfile, b: TeamProfile) => (b.ovr ?? -1) - (a.ovr ?? -1);
  const val = (k: "ovr" | "off" | "def") => (a: TeamProfile, b: TeamProfile) => (b[k] ?? -1) - (a[k] ?? -1) || byOvr(a, b);
  const shown = teams.filter((tm) => (off == null || tm.style_id === off) && (def == null || tm.defense_tag === def)).sort(
    sort === "division" ? (a, b) => divisionOf(a.team) - divisionOf(b.team) || byOvr(a, b)
    : sort === "rank" ? (a, b) => (conf.get(a.team) ?? 9) - (conf.get(b.team) ?? 9) || (rank.get(a.team) ?? 99) - (rank.get(b.team) ?? 99) || byOvr(a, b)
    : val(sort));
  const card = (tm: TeamProfile) => (
    <TeamCard key={tm.team} t={tm} season={season} archetypes={archetypes} style={styleOf.get(tm.style_id)} rank={sort === "rank" ? rank.get(tm.team) : undefined} />
  );
  const grid = { display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 270px), 1fr))" } as const;
  const sections = sort === "division" ? DIVISIONS.map(([zh, en], i) => ({ title: lang === "zh" ? zh : en, teams: shown.filter((tm) => divisionOf(tm.team) === i) }))
    : sort === "rank" && conf.size ? [["东部", 0], ["西部", 1]].map(([zh, c]) => ({ title: t(zh as string), teams: shown.filter((tm) => conf.get(tm.team) === c) }))
    : [{ title: "", teams: shown }];
  const picked = off == null ? undefined : styleOf.get(off);
  return (
    <>
      {early && <p className="bubble" style={{ margin: 0 }}>{t("赛季初过渡值：进攻体系和球队评分按场次把本赛季和上赛季合成（本赛季权重 = 场次 ÷（场次 + 20）），轮换和风格还会变化。")}</p>}
      <div className="row">
        <InfoButton label={t("进攻体系")} onClick={() => setInfo("off")} />
        <span className="note" style={{ minWidth: "5em" }}>{t("进攻体系")}</span>
        <button type="button" className="chip" aria-pressed={off === null} onClick={() => setOff(null)}>{t("全部")}</button>
        {styles.map((s) => (
          <button key={s.style_id} type="button" className="chip" aria-pressed={off === s.style_id}
            onClick={() => setOff(off === s.style_id ? null : s.style_id)}>
            {name(s.name)} <span style={{ color: "var(--muted)" }}>{teams.filter((tm) => tm.style_id === s.style_id).length}</span>
          </button>
        ))}
      </div>
      <div className="row">
        <InfoButton label={t("防守体系")} onClick={() => setInfo("def")} />
        <span className="note" style={{ minWidth: "5em" }}>{t("防守体系")}</span>
        <button type="button" className="chip" aria-pressed={def === null} onClick={() => setDef(null)}>{t("全部")}</button>
        {defTags.map((d) => (
          <button key={d} type="button" className="chip" aria-pressed={def === d} onClick={() => setDef(def === d ? null : d)}>
            {name(d)} <span style={{ color: "var(--muted)" }}>{teams.filter((tm) => tm.defense_tag === d).length}</span>
          </button>
        ))}
      </div>
      {picked?.description && <p style={{ margin: 0, maxWidth: "70ch" }}>{t(picked.description)}</p>}
      <Modal open={info === "off"} onClose={() => setInfo(null)} title={t("进攻体系")}>
        <p style={{ margin: 0 }}>{t("进攻体系看的是球队怎么打：战术类型占比（挡拆、单打、空切、背身……）、传球和触球、突破、出手分布和节奏，都和当季联盟比，再用 2015-16 以来的全部球队聚成 5 类。打法是连续的，归类表示「最接近」，不是严格的派系。")}</p>
        <p style={{ margin: 0 }}>{t("「球员构成」是轮换 9 人的打法原型按分钟加权。")} {t("交易过的球员算在他最后效力的球队。")}</p>
        <p style={{ margin: 0 }}>{t("球队评分（综合、进攻、防守）一半来自轮换球员的评分（按分钟加权），一半来自球队实际的每百回合净胜分、得分和失分，各自在当季 30 队里排名，80 分是联盟平均。")}</p>
        <StyleTable styles={styles} pick={off} onPick={setOff} />
      </Modal>
      <Modal open={info === "def"} onClose={() => setInfo(null)} title={t("防守体系")}>
        <p style={{ margin: 0 }}>{t("防守体系看的是球队的轮换更依赖哪一种防守方式。每名球员的防守特征（抢断、干扰、护框次数、封盖、造犯规、对位三分和近筐出手占比、防守速度等）先归成 4 种防守原型，每人是这几种原型的混合。")}</p>
        <p style={{ margin: 0 }}>{t("球队的防守构成是轮换 9 人的防守原型按分钟加权，再和当季联盟比；标签取这支球队比联盟平均更突出的那一种。它是「最偏向」，不是球队唯一的防守方式，也不是聚类分出来的派系。")}</p>
        <ul style={{ margin: 0, paddingLeft: "1.2em", display: "grid", gap: 4 }}>
          <li><b>{t("护框型防守")}</b>：{t("轮换里护框、封盖多，保护内线。")}</li>
          <li><b>{t("侵略型防守")}</b>：{t("抢断、干扰多，靠主动出击制造失误。")}</li>
          <li><b>{t("外线封堵型防守")}</b>：{t("防外线投手，封盖三分出手。")}</li>
          <li><b>{t("追防型防守")}</b>：{t("防守速度快、对位多，常被对手针对。")}</li>
        </ul>
        <p style={{ margin: 0 }}>{t("球队评分里的「防守」一半来自轮换球员的防守评分，一半来自球队实际的每百回合失分。")}</p>
      </Modal>
      <div className="row">
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("排序")}
          <select className="select" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </select>
        </label>
        <span className="note">{t("{n} 支球队", { n: shown.length })}</span>
      </div>
      {sections.map((sec) => sec.teams.length > 0 && (
        <section key={sec.title} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {sec.title && <span className="caption" style={{ fontSize: 20 }}>{sec.title}</span>}
          <div style={grid}>{sec.teams.map(card)}</div>
        </section>
      ))}
    </>
  );
}
