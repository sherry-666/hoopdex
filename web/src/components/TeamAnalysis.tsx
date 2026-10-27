import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MatchupCell, seriesColor, TeamProfile, TeamStyle, useMatchups, useTeams } from "../api";
import { useLang } from "../i18n";
import { DEFENSE_TAGS, FEATURE_GROUPS, shade, signature, signed, teamFeature } from "../teamFeatures";
import MatchupMatrix from "./MatchupMatrix";
import { teamName } from "../teams";

const N = (v: number | null | undefined) => (v == null ? "—" : String(Math.round(v)));

/** 1 = best: how many teams have a higher value (or a lower one, when lowerIsBetter). */
function rankOf(teams: TeamProfile[], team: string, value: (t: TeamProfile) => number | null | undefined, lowerIsBetter = false) {
  const mine = teams.find((t) => t.team === team);
  const v = mine && value(mine);
  if (v == null) return null;
  const all = teams.map(value).filter((x): x is number => x != null);
  return { rank: 1 + all.filter((x) => (lowerIsBetter ? x < v : x > v)).length, of: all.length };
}

function Stat({ label, value, rank }: { label: string; value: string; rank: { rank: number; of: number } | null }) {
  const { t } = useLang();
  return (
    <div style={{ display: "grid", gap: 2 }}>
      <span className="note">{label}</span>
      <b style={{ fontSize: 20, fontFamily: "var(--font-latin)" }}>{value}</b>
      {rank && <span className="note">{t("联盟第 {n}", { n: rank.rank })} / {rank.of}</span>}
    </div>
  );
}

/** A bar from the league average (centre) to this team's value, with a tick for the group average. */
function ZBar({ z, mark, max = 2.5 }: { z: number; mark?: number; max?: number }) {
  const pos = (v: number) => 50 + (Math.max(-max, Math.min(max, v)) / max) * 50;
  const left = Math.min(50, pos(z));
  return (
    <div style={{ position: "relative", height: 14, background: "color-mix(in srgb, var(--ink) 8%, var(--panel))", border: "1.5px solid var(--ink)" }}>
      <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1.5, background: "var(--ink)", opacity: 0.5 }} />
      <div style={{ position: "absolute", left: `${left}%`, width: `${Math.abs(pos(z) - 50)}%`, top: 0, bottom: 0,
        background: z >= 0 ? "var(--seq-hi)" : "var(--seq-lo)" }} />
      {mark != null && <div style={{ position: "absolute", left: `${pos(mark)}%`, top: -3, bottom: -3, width: 3, background: "var(--ink)" }} />}
    </div>
  );
}

function FeatureRow({ code, z, mark, teams, team }: { code: string; z: number; mark?: number; teams: TeamProfile[]; team: string }) {
  const { lang } = useLang();
  const r = rankOf(teams, team, (t) => t.system?.[code]);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(80px, 1.1fr) 2fr 5.5em", gap: 8, alignItems: "center", fontSize: "var(--size-caption)" }}>
      <span>{teamFeature(code, lang)}</span>
      <ZBar z={z} mark={mark} />
      <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {z > 0 ? "+" : z < 0 ? "−" : ""}{Math.abs(z).toFixed(1)}σ {r && <span className="note">#{r.rank}</span>}
      </span>
    </div>
  );
}

function OffenseCard({ me, teams, styles, season }: { me: TeamProfile; teams: TeamProfile[]; styles: TeamStyle[]; season: string }) {
  const { t, name } = useLang();
  const [all, setAll] = useState(false);
  const style = styles.find((s) => s.style_id === me.style_id);
  const sys = me.system;
  const peers = teams.filter((x) => x.style_id === me.style_id && x.team !== me.team);
  return (
    <article className="panel" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <span className="caption" style={{ background: "var(--pop-yellow)" }}>{t("进攻体系")} · {name(style?.name ?? "")}</span>
        {style?.description && <p style={{ margin: "8px 0 0" }}>{t(style.description)}</p>}
      </div>
      <div className="row" style={{ gap: 24 }}>
        <Stat label={t("进攻评分")} value={N(me.off)} rank={rankOf(teams, me.team, (x) => x.off)} />
        <Stat label={t("每百回合得分")} value={me.ortg?.toFixed(1) ?? "—"} rank={rankOf(teams, me.team, (x) => x.ortg)} />
        {sys?.pace != null && <Stat label={t("节奏")} value={`${sys.pace > 0 ? "+" : sys.pace < 0 ? "−" : ""}${Math.abs(sys.pace).toFixed(1)}σ`} rank={rankOf(teams, me.team, (x) => x.system?.pace)} />}
      </div>
      {sys ? (
        <div style={{ display: "grid", gap: 6 }}>
          <div className="note">{t("相对当季联盟的特点（σ；黑色竖线是同体系球队的平均；# 是联盟排名）")}</div>
          {(all
            ? FEATURE_GROUPS.flatMap(([, codes]) => codes).filter((c) => c in sys).map((c): [string, number] => [c, sys[c]])
            : signature(sys, 8)
          ).map(([code, z]) => <FeatureRow key={code} code={code} z={z} mark={style?.centroid[code]} teams={teams} team={me.team} />)}
          <button type="button" className="chip" style={{ justifySelf: "start" }} onClick={() => setAll(!all)}>
            {all ? t("只看最突出的 8 项") : t("展开全部特征")}
          </button>
        </div>
      ) : <p className="note">{t("这个赛季没有球队层面的打法数据。")}</p>}
      {peers.length > 0 && (
        <div>
          <div className="note" style={{ marginBottom: 4 }}>{t("同体系的球队")}</div>
          <div className="row" style={{ gap: 6 }}>
            {peers.sort((a, b) => (b.off ?? 0) - (a.off ?? 0)).map((p) => <PeerChip key={p.team} p={p} metric="off" season={season} />)}
          </div>
        </div>
      )}
    </article>
  );
}

function PeerChip({ p, metric, season }: { p: TeamProfile; metric: "off" | "def"; season: string }) {
  const { lang } = useLang();
  return (
    <Link className="chip" to={`/teams/${p.team}?season=${season}`}>
      {teamName(p.team, lang, false)} <span style={{ color: "var(--muted)" }}>{N(p[metric])}</span>
    </Link>
  );
}

function DefenseCard({ me, teams, defenseNames, season }: { me: TeamProfile; teams: TeamProfile[]; defenseNames: string[]; season: string }) {
  const { t, name } = useLang();
  const peers = teams.filter((x) => x.defense_tag === me.defense_tag && x.team !== me.team);
  const avg = (k: string) => teams.reduce((s, x) => s + (x.def_mix[k] ?? 0), 0) / teams.length;
  return (
    <article className="panel" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <span className="caption">{t("防守体系")} · {name(me.defense_tag)}</span>
        <p style={{ margin: "8px 0 0" }}>{t("轮换里哪一类防守球员最多：比联盟平均更突出的那一类决定了标签。")}</p>
      </div>
      <div className="row" style={{ gap: 24 }}>
        <Stat label={t("防守评分")} value={N(me.def)} rank={rankOf(teams, me.team, (x) => x.def)} />
        <Stat label={t("每百回合失分")} value={me.drtg?.toFixed(1) ?? "—"} rank={rankOf(teams, me.team, (x) => x.drtg, true)} />
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        <div className="note">{t("轮换的防守构成（按分钟加权；黑色竖线是联盟平均；# 是联盟排名）")}</div>
        {defenseNames.map((d) => {
          const share = me.def_mix[d] ?? 0;
          const mean = avg(d);
          const r = rankOf(teams, me.team, (x) => x.def_mix[d]);
          const tag = DEFENSE_TAGS[d] ?? d;
          return (
            <div key={d} style={{ display: "grid", gridTemplateColumns: "minmax(80px, 1.1fr) 2fr 7.5em", gap: 8, alignItems: "center", fontSize: "var(--size-caption)" }}>
              <span style={{ fontWeight: tag === me.defense_tag ? 700 : 400 }}>{name(tag)}</span>
              <div style={{ position: "relative", height: 14, background: "color-mix(in srgb, var(--ink) 8%, var(--panel))", border: "1.5px solid var(--ink)" }}>
                <div style={{ position: "absolute", left: 0, width: `${Math.min(100, share * 100 * 2)}%`, top: 0, bottom: 0, background: "var(--series-3)" }} />
                <div style={{ position: "absolute", left: `${Math.min(100, mean * 100 * 2)}%`, top: -3, bottom: -3, width: 3, background: "var(--ink)" }} />
              </div>
              <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {Math.round(share * 100)}% <span className="note">{t("均值 {n}%", { n: Math.round(mean * 100) })} {r && `#${r.rank}`}</span>
              </span>
            </div>
          );
        })}
      </div>
      {peers.length > 0 && (
        <div>
          <div className="note" style={{ marginBottom: 4 }}>{t("同防守体系的球队")}</div>
          <div className="row" style={{ gap: 6 }}>
            {peers.sort((a, b) => (b.def ?? 0) - (a.def ?? 0)).map((p) => <PeerChip key={p.team} p={p} metric="def" season={season} />)}
          </div>
        </div>
      )}
    </article>
  );
}

/** This team's two systems read off the matchup table: how its offence fares against each defence, and its defence against each offence. */
function MatchupCard({ me, styles }: { me: TeamProfile; styles: TeamStyle[] }) {
  const { t, name } = useLang();
  const q = useMatchups();
  if (!q.data?.meta) return null;
  const { cells } = q.data;
  const solid = (q.data.meta?.p_value ?? 1) < 0.05;   // otherwise the cells are noise: say so, do not list them
  const mineOff = cells.filter((c) => c.off_style === me.style_id);
  const mineDef = cells.filter((c) => c.def_tag === me.defense_tag);
  const chip = (label: string, c: MatchupCell, effect: number) => (
    <span key={label} className="tag" style={{ background: shade(effect, 1.6), color: Math.abs(effect) > 1.3 ? "#fff" : "var(--ink)", fontVariantNumeric: "tabular-nums" }}
      title={t("原始 {raw} 分，误差 ±{se}，{n} 场", { raw: signed(c.raw_effect), se: c.se.toFixed(1), n: c.n })}>
      {label} {signed(effect)}
    </span>
  );
  return (
    <section className="panel" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <span className="caption" style={{ alignSelf: "flex-start" }}>{t("克制关系")}</span>
      {solid && (
        <>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>
              {t("{style} 进攻面对不同防守：每场得分比预期多 / 少", { style: name(styles.find((s) => s.style_id === me.style_id)?.name ?? "") })}
            </div>
            <div className="row" style={{ gap: 6 }}>{mineOff.map((c) => chip(name(c.def_tag), c, c.effect))}</div>
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>
              {t("{tag} 面对不同进攻：对手得分比预期多 / 少（负 = 防守占优）", { tag: name(me.defense_tag) })}
            </div>
            <div className="row" style={{ gap: 6 }}>
              {mineDef.map((c) => chip(name(styles.find((s) => s.style_id === c.off_style)?.name ?? ""), c, c.effect))}
            </div>
          </div>
        </>
      )}
      <MatchupMatrix offStyle={me.style_id} defTag={me.defense_tag} />
    </section>
  );
}

/** Every team as a dot by offense and defense rating; this one highlighted, colour = offensive system. */
function LeagueScatter({ me, teams, season }: { me: TeamProfile; teams: TeamProfile[]; season: string }) {
  const { t, lang } = useLang();
  const nav = useNavigate();
  const rated = teams.filter((x) => x.off != null && x.def != null);
  if (!rated.length) return null;
  const W = 640, H = 380, pad = { l: 46, r: 16, t: 14, b: 40 };
  const lo = (k: "off" | "def") => Math.floor(Math.min(...rated.map((x) => x[k]!)) / 2) * 2 - 2;
  const hi = (k: "off" | "def") => Math.ceil(Math.max(...rated.map((x) => x[k]!)) / 2) * 2 + 2;
  const x0 = lo("off"), x1 = hi("off"), y0 = lo("def"), y1 = hi("def");
  const sx = (v: number) => pad.l + ((v - x0) / (x1 - x0)) * (W - pad.l - pad.r);
  const sy = (v: number) => H - pad.b - ((v - y0) / (y1 - y0)) * (H - pad.t - pad.b);
  return (
    <section className="panel" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span className="caption" style={{ alignSelf: "flex-start" }}>{t("联盟对比：进攻评分 × 防守评分")}</span>
      <p className="note" style={{ margin: 0 }}>{t("每个点是一支球队，越靠右上两端越强；颜色是进攻体系，80 分是联盟平均。点击球队进入它的页面。")}</p>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("联盟对比：进攻评分 × 防守评分")} style={{ width: "100%", maxWidth: 760, height: "auto" }}>
        <rect x={pad.l} y={pad.t} width={W - pad.l - pad.r} height={H - pad.t - pad.b} fill="none" stroke="var(--ink)" strokeWidth="1.5" />
        {x0 < 80 && x1 > 80 && <line x1={sx(80)} x2={sx(80)} y1={pad.t} y2={H - pad.b} stroke="var(--muted)" strokeDasharray="4 4" />}
        {y0 < 80 && y1 > 80 && <line x1={pad.l} x2={W - pad.r} y1={sy(80)} y2={sy(80)} stroke="var(--muted)" strokeDasharray="4 4" />}
        <text x={(pad.l + W - pad.r) / 2} y={H - 8} textAnchor="middle" fontSize="12" fill="var(--muted)">{t("进攻评分")} →</text>
        <text x={12} y={(pad.t + H - pad.b) / 2} textAnchor="middle" fontSize="12" fill="var(--muted)" transform={`rotate(-90 12 ${(pad.t + H - pad.b) / 2})`}>{t("防守评分")} →</text>
        {[x0, x1].map((v) => <text key={`x${v}`} x={sx(v)} y={H - pad.b + 14} textAnchor="middle" fontSize="11" fill="var(--muted)">{v}</text>)}
        {[y0, y1].map((v) => <text key={`y${v}`} x={pad.l - 6} y={sy(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{v}</text>)}
        {rated.filter((x) => x.team !== me.team).map((x) => (
          <g key={x.team} style={{ cursor: "pointer" }} onClick={() => nav(`/teams/${x.team}?season=${season}`)}>
            <title>{teamName(x.team, lang, true)} · {t("进攻")} {x.off} · {t("防守")} {x.def}</title>
            <circle cx={sx(x.off!)} cy={sy(x.def!)} r={6} fill={seriesColor(x.style_id)} stroke="var(--ink)" strokeWidth="1.2" opacity="0.75" />
            <text x={sx(x.off!)} y={sy(x.def!) - 9} textAnchor="middle" fontSize="10" fill="var(--muted)">{x.team}</text>
          </g>
        ))}
        <g>
          <title>{teamName(me.team, lang, true)} · {t("进攻")} {me.off} · {t("防守")} {me.def}</title>
          <circle cx={sx(me.off!)} cy={sy(me.def!)} r={10} fill={seriesColor(me.style_id)} stroke="var(--ink)" strokeWidth="3" />
          <text x={sx(me.off!)} y={sy(me.def!) - 15} textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--ink)">{me.team}</text>
        </g>
      </svg>
    </section>
  );
}

export default function TeamAnalysis({ team, season }: { team: string; season: string }) {
  const { t } = useLang();
  const view = useTeams(season);
  if (!view.data) return null;
  const { teams, styles, archetypes } = view.data;
  const me = teams.find((x) => x.team === team);
  if (!me) return null;
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <span className="caption" style={{ fontSize: 20, alignSelf: "flex-start" }}>{t("体系分析")}</span>
      <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))" }}>
        <OffenseCard me={me} teams={teams} styles={styles} season={season} />
        <DefenseCard me={me} teams={teams} defenseNames={archetypes.defense} season={season} />
      </div>
      <MatchupCard me={me} styles={styles} />
      <LeagueScatter me={me} teams={teams} season={season} />
    </section>
  );
}
