import { Link, useParams } from "react-router-dom";
import { TeamPageData, TeamRosterRow, useDefaultSeason, useTeamPage } from "../api";
import { Failed, Loading, TeamLogo } from "../components/comic";
import { OffDef, OvrBadge } from "../components/rating";
import { useLang, usePageTitle } from "../i18n";
import { teamName } from "../teams";
import { InjuryMark } from "./TeamPage";

const ROSTER_SHOWN = 10;

function Head({ data, team, align }: { data: TeamPageData; team: string; align: "left" | "right" }) {
  const { t, name, lang } = useLang();
  const p = data.profile, st = data.standing;
  return (
    <div style={{ textAlign: align }}>
      <h2 style={{ fontSize: "var(--size-h2)" }}>
        <Link to={`/teams/${team}`} style={{ color: "inherit" }}><TeamLogo team={team} size={44} />{teamName(team, lang, true)}</Link>
      </h2>
      <div className="row" style={{ gap: 6, marginTop: 6, justifyContent: align === "left" ? "flex-start" : "flex-end", flexWrap: "wrap" }}>
        {p.style_name && <span className="tag" style={{ background: "var(--pop-yellow)", color: "var(--on-yellow)" }}>{t("攻")} · {name(p.style_name)}</span>}
        <span className="tag" style={{ color: "var(--ink)" }}>{t("守")} · {name(p.defense_tag)}</span>
      </div>
      {st && <p className="note" style={{ margin: "6px 0 0" }}>{st.wins}-{st.losses} · {st.conf === "East" ? t("东部") : t("西部")} #{st.rank}</p>}
    </div>
  );
}

/** One comparison line: left value, label in the middle, right value; the better side is bold. */
function Line({ label, a, b, higherIsBetter = true, digits = 1 }: { label: string; a: number | null | undefined; b: number | null | undefined; higherIsBetter?: boolean; digits?: number }) {
  const fmt = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(digits));
  const better = a == null || b == null || a === b ? 0 : (a > b) === higherIsBetter ? -1 : 1;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 12, padding: "6px 0", borderBottom: "1px dashed var(--ink)" }}>
      <span className="num" style={{ textAlign: "right", fontWeight: better === -1 ? 800 : 400 }}>{fmt(a)}</span>
      <span className="note" style={{ minWidth: 96, textAlign: "center" }}>{label}</span>
      <span className="num" style={{ fontWeight: better === 1 ? 800 : 400 }}>{fmt(b)}</span>
    </div>
  );
}

function Roster({ data }: { data: TeamPageData }) {
  const { t, name } = useLang();
  const rows = data.roster.filter((r: TeamRosterRow) => !r.departed).slice(0, ROSTER_SHOWN);
  return (
    <div className="table-box">
      <table className="data">
        <thead><tr><th style={{ textAlign: "left" }}>{t("球员")}</th><th className="num-col">{t("综合")}</th><th className="hide-narrow" style={{ textAlign: "left" }}>{t("打法")}</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.player_id}>
              <td><Link to={`/players/${r.player_id}?season=${data.season}`}>{r.name}</Link>{r.injury && <InjuryMark injury={r.injury} avail={r.avail} />}</td>
              <td className="num-col"><OvrBadge ovr={r.ovr} size={28} /></td>
              <td className="hide-narrow">{[r.off_style, r.def_style].filter(Boolean).map((s) => name(s as string)).join(" · ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Matchup() {
  const { t, lang } = useLang();
  const params = useParams();
  const away = (params.away ?? "").toUpperCase(), home = (params.home ?? "").toUpperCase();
  const season = useDefaultSeason();
  const a = useTeamPage(away, season), h = useTeamPage(home, season);
  usePageTitle(`${teamName(away, lang, true)} @ ${teamName(home, lang, true)}`);
  if (!season || a.isLoading || h.isLoading) return <Loading what="球队" />;
  if (a.error || h.error || !a.data || !h.data) return <Failed error={a.error ?? h.error} />;
  const pa = a.data.profile, ph = h.data.profile, sa = a.data.standing, sh = h.data.standing;
  return (
    <>
      <p><Link to="/predict">← {t("比赛预测")}</Link></p>
      <section className="panel halftone" style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 16, alignItems: "center" }}>
        <Head data={a.data} team={away} align="left" />
        <span className="caption">@</span>
        <Head data={h.data} team={home} align="right" />
      </section>

      <section className="panel">
        <span className="caption" style={{ fontSize: 20 }}>{t("球队对比")}</span>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 12, padding: "10px 0" }}>
          <span style={{ textAlign: "right" }}><OvrBadge ovr={pa.ovr} size={44} /></span>
          <span className="note" style={{ minWidth: 96, textAlign: "center", alignSelf: "center" }}>{t("综合")}</span>
          <span><OvrBadge ovr={ph.ovr} size={44} /></span>
          <span style={{ textAlign: "right" }}><OffDef off={pa.off} def={pa.def} /></span>
          <span className="note" style={{ textAlign: "center" }}>{t("攻 / 守")}</span>
          <span><OffDef off={ph.off} def={ph.def} /></span>
        </div>
        <Line label={t("进攻效率")} a={pa.ortg} b={ph.ortg} />
        <Line label={t("防守效率")} a={pa.drtg} b={ph.drtg} higherIsBetter={false} />
        {sa && sh && <Line label={t("场均得分")} a={sa.pts_for} b={sh.pts_for} />}
        {sa && sh && <Line label={t("场均失分")} a={sa.pts_against} b={sh.pts_against} higherIsBetter={false} />}
        {sa && sh && <Line label={t("胜率")} a={sa.win_pct == null ? null : sa.win_pct * 100} b={sh.win_pct == null ? null : sh.win_pct * 100} digits={0} />}
      </section>

      <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))" }}>
        <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span className="caption" style={{ fontSize: 20, alignSelf: "flex-start" }}>{teamName(away, lang, true)} · {t("阵容")}</span>
          <Roster data={a.data} />
        </section>
        <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span className="caption" style={{ fontSize: 20, alignSelf: "flex-start" }}>{teamName(home, lang, true)} · {t("阵容")}</span>
          <Roster data={h.data} />
        </section>
      </div>
    </>
  );
}
