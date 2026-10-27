import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { TeamGame, TeamRosterRow, useDefaultSeason, useTeamPage, useTeamSeasons } from "../api";
import { Failed, Loading, SeasonSelect, TeamLogo } from "../components/comic";
import { OffDef, OvrBadge } from "../components/rating";
import { useLang, usePageTitle } from "../i18n";
import { injuryWhere } from "../labels";
import { teamName } from "../teams";

const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

/** "2025-10-22" as a short local date; parsed as a calendar date so the time zone cannot shift it. */
function shortDate(iso: string, lang: "zh" | "en") {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(lang === "zh" ? "zh-CN" : "en-US", { month: "short", day: "numeric", weekday: "short" });
}

/** Red cross next to an injured player; hover or focus for status, body part and expected return. */
function InjuryMark({ injury, avail }: { injury: NonNullable<TeamRosterRow["injury"]>; avail: number }) {
  const { t, lang } = useLang();
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  const where = injuryWhere(injury, lang);
  const out = injury.status === "Out";
  const show = (el: Element) => {
    const r = el.getBoundingClientRect();
    setAt({ x: Math.min(r.left, window.innerWidth - 300), y: r.bottom + 6 });
  };
  return (
    <span tabIndex={0} role="img" aria-label={`${out ? t("伤停") : t("出战成疑")} ${where ?? ""}`}
      onMouseEnter={(e) => show(e.currentTarget)} onMouseLeave={() => setAt(null)}
      onFocus={(e) => show(e.currentTarget)} onBlur={() => setAt(null)}
      style={{ display: "inline-block", marginLeft: 6, verticalAlign: "-2px", cursor: "help" }}>
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M6 1h4v5h5v4h-5v5H6v-5H1V6h5z" fill="var(--pop-red)" stroke="var(--ink)" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
      {at && (
        <div className="panel" style={{ position: "fixed", left: at.x, top: at.y, width: 280, zIndex: 50, margin: 0, padding: "10px 12px", background: "var(--panel)",
          borderColor: out ? "var(--pop-red)" : "var(--pop-yellow)", textAlign: "left", fontWeight: 400, pointerEvents: "none" }}>
          <div className="row" style={{ gap: 8 }}>
            <span className="tag" style={{ background: out ? "var(--pop-red)" : "var(--pop-yellow)", color: out ? "#fff" : "var(--on-yellow)", fontWeight: 700 }}>
              {out ? t("伤停") : t("出战成疑")}
            </span>
            {where && <b>{where}{injury.detail && lang === "en" ? ` · ${injury.detail}` : ""}</b>}
          </div>
          <div style={{ marginTop: 6 }}>
            {injury.return_date ? t("预计 {date} 前后复出", { date: injury.return_date }) : t("复出时间未定")}
          </div>
          {avail < 1 && (
            <div className="note" style={{ marginTop: 6 }}>
              {avail === 0 ? t("伤停超过一个月：不计入球队的评分和阵容构成。") : t("球队评分里按 {pct}% 计算。", { pct: Math.round(avail * 100) })}
            </div>
          )}
          {injury.short_comment && <p className="note" style={{ margin: "6px 0 0" }}>{injury.short_comment}</p>}
        </div>
      )}
    </span>
  );
}

function GameRow({ g, season }: { g: TeamGame; season: string }) {
  const { t, lang } = useLang();
  const won = g.completed && g.team_score != null && g.opp_score != null && g.team_score > g.opp_score;
  return (
    <tr>
      <td>{shortDate(g.game_date, lang)}</td>
      <td>
        <Link to={`/teams/${g.opp}?season=${season}`}>
          <span className="note">{g.home ? t("主") : t("客")} </span>
          <TeamLogo team={g.opp} size={22} />{teamName(g.opp, lang, lang === "en")}
        </Link>
        {g.season_type === 3 && <span className="tag" style={{ marginLeft: 6 }}>{t("季后赛")}</span>}
      </td>
      <td className="num-col">
        {g.completed ? (
          <>
            <span className="tag" style={won ? { background: "var(--pop-yellow)", color: "var(--on-yellow)" } : undefined}>{won ? t("胜") : t("负")}</span>{" "}
            {g.team_score}–{g.opp_score}
          </>
        ) : (
          <span className="note">{new Date(g.tipoff).toLocaleTimeString(lang === "zh" ? "zh-CN" : "en-US", { hour: "2-digit", minute: "2-digit" })}</span>
        )}
      </td>
    </tr>
  );
}

function GameTable({ games, season, empty }: { games: TeamGame[]; season: string; empty: string }) {
  const { t } = useLang();
  if (!games.length) return <p className="note">{empty}</p>;
  return (
    <div className="table-box" style={{ maxHeight: 520 }}>
      <table className="data">
        <thead><tr><th style={{ textAlign: "left" }}>{t("日期")}</th><th style={{ textAlign: "left" }}>{t("对手")}</th><th className="num-col">{t("比分")}</th></tr></thead>
        <tbody>{games.map((g) => <GameRow key={g.game_id} g={g} season={season} />)}</tbody>
      </table>
    </div>
  );
}

export default function TeamPage() {
  const { t, name, lang } = useLang();
  const team = (useParams().team ?? "").toUpperCase();
  const [params, setParams] = useSearchParams();
  const seasons = useTeamSeasons(team);
  const defaultSeason = useDefaultSeason();
  const season = params.get("season") ?? (seasons.data?.includes(defaultSeason ?? "") ? defaultSeason : seasons.data?.[0]);
  const q = useTeamPage(team, season);
  usePageTitle(season ? t("{team} {season} 阵容、评分与赛程", { team: teamName(team, lang, true), season }) : undefined);
  if (seasons.isLoading || q.isLoading || !season) return <Loading what="球队" />;
  if (seasons.data && !seasons.data.length) return <Failed error={t("没有这支球队")} />;
  if (q.error || !q.data) return <Failed error={q.error} />;
  const { profile: p, standing: st, roster, games } = q.data;
  const played = games.filter((g) => g.completed).reverse();
  const upcoming = games.filter((g) => !g.completed);
  const setSeason = (s: string) => {
    const next = new URLSearchParams(params);
    next.set("season", s);
    setParams(next, { replace: true });
  };
  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-red)", color: "#fff", borderColor: "#111" }}>
        <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ fontSize: "var(--size-h1)" }}><TeamLogo team={team} size={56} />{teamName(team, lang, true)}</h1>
            <div className="row" style={{ gap: 6, marginTop: 8 }}>
              {p.style_name && <span className="tag" style={{ background: "var(--pop-yellow)", color: "var(--on-yellow)" }}>{t("攻")} · {name(p.style_name)}</span>}
              <span className="tag" style={{ color: "var(--ink)" }}>{t("守")} · {name(p.defense_tag)}</span>
              {st && <span className="tag" style={{ color: "var(--ink)" }}>{st.conf === "East" ? t("东部") : t("西部")} #{st.rank}</span>}
            </div>
            {st && (
              <p style={{ margin: "8px 0 0" }}>
                {st.wins}–{st.losses}
                {st.home && st.road && <> · {t("主场")} {st.home} · {t("客场")} {st.road}</>}
                {st.last10 && <> · {t("近10场")} {st.last10}</>}
                {st.streak && <> · {st.streak}</>}
              </p>
            )}
          </div>
          <div className="row" style={{ gap: 14, color: "var(--ink)" }}>
            <div style={{ textAlign: "center", display: "grid", justifyItems: "center", gap: 4 }}>
              <OvrBadge ovr={p.ovr} size={64} />
              <div className="note" style={{ color: "#fff" }}>{t("球队评分")}</div>
            </div>
            <OffDef off={p.off} def={p.def} size={18} />
          </div>
        </div>
        {p.ortg != null && p.drtg != null && (
          <p style={{ margin: "8px 0 0" }}>{t("得 {o} · 失 {d} / 百回合", { o: p.ortg.toFixed(1), d: p.drtg.toFixed(1) })}</p>
        )}
      </section>
      <div className="row">
        <SeasonSelect value={season} seasons={seasons.data} onChange={setSeason} />
        <Link to={`/teams?season=${season}`} className="note">{t("← 全部球队体系")}</Link>
        <Link to={`/rankings?season=${season}`} className="note">{t("排名")}</Link>
      </div>

      <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span className="caption" style={{ fontSize: 20, alignSelf: "flex-start" }}>{t("球员阵容与数据")}</span>
        <p className="note" style={{ margin: 0 }}>{t("本赛季为这支球队打过球的球员，按上场时间排序；场均数据是他在这支球队的常规赛场均。")}</p>
        {roster.some((r) => r.avail < 1) && (
          <p className="note" style={{ margin: 0 }}>
            {t("球队评分和阵容构成会考虑伤病：伤停超过一个月的球员（{names}）不计入，较短的缺阵按出战比例折算。", {
              names: roster.filter((r) => r.avail === 0).map((r) => r.name).join(t("、")) || t("无"),
            })}
          </p>
        )}
        <div className="table-box" style={{ maxHeight: "none" }}>
          <table className="data" style={{ minWidth: 640 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>{t("球员")}</th>
                <th className="num-col">{t("综合")}</th>
                <th className="num-col">{t("攻")}</th>
                <th className="num-col">{t("守")}</th>
                <th style={{ textAlign: "left" }} className="hide-narrow">{t("打法")}</th>
                <th className="num-col">{t("场次")}</th>
                <th className="num-col">{t("得分")}</th>
                <th className="num-col">{t("篮板")}</th>
                <th className="num-col">{t("助攻")}</th>
                <th className="num-col hide-narrow">{t("真实命中率")}</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((r) => (
                <tr key={r.player_id}>
                  <td><Link to={`/players/${r.player_id}?season=${season}`}>{r.name}</Link>{r.departed && <span className="tag" style={{ marginLeft: 6 }}>{t("已离队")}</span>}{r.injury && <InjuryMark injury={r.injury} avail={r.avail} />}</td>
                  <td className="num-col"><OvrBadge ovr={r.ovr} size={30} /></td>
                  <td className="num-col">{r.off ?? "—"}</td>
                  <td className="num-col">{r.def ?? "—"}</td>
                  <td className="hide-narrow">{[r.off_style, r.def_style].filter(Boolean).map((s) => name(s as string)).join(" · ")}</td>
                  <td className="num-col">{r.gp}</td>
                  <td className="num-col">{r.pts?.toFixed(1) ?? "—"}</td>
                  <td className="num-col">{r.reb?.toFixed(1) ?? "—"}</td>
                  <td className="num-col">{r.ast?.toFixed(1) ?? "—"}</td>
                  <td className="num-col hide-narrow">{pct(r.ts_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))" }}>
        {upcoming.length > 0 && (
        <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span className="caption" style={{ fontSize: 20, alignSelf: "flex-start" }}>{t("未来赛程")} · {upcoming.length}</span>
          <GameTable games={upcoming} season={season} empty="" />
        </section>
        )}
        <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span className="caption" style={{ fontSize: 20, alignSelf: "flex-start" }}>{t("已打比赛")} · {played.length}</span>
          <GameTable games={played} season={season} empty={t("还没有打过比赛。")} />
        </section>
      </div>
    </>
  );
}
