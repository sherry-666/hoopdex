import { Link } from "react-router-dom";
import { PlayerHonor, TeamHonorRow, usePlayerHonors, useTeamHonors } from "../api";
import { useLang } from "../i18n";

/* Award names as stats.nba.com spells them, most prestigious first: [Chinese, English]. */
const AWARDS: Record<string, [string, string]> = {
  "NBA Champion": ["总冠军", "NBA Champion"],
  "NBA Most Valuable Player": ["常规赛 MVP", "Regular-season MVP"],
  "NBA Finals Most Valuable Player": ["总决赛 MVP", "Finals MVP"],
  "NBA Defensive Player of the Year": ["最佳防守球员", "Defensive Player of the Year"],
  "NBA Rookie of the Year": ["最佳新秀", "Rookie of the Year"],
  "NBA Most Improved Player": ["进步最快球员", "Most Improved Player"],
  "NBA Sixth Man of the Year": ["最佳第六人", "Sixth Man of the Year"],
  "NBA Clutch Player of the Year": ["最佳关键球员", "Clutch Player of the Year"],
  "NBA Scoring Champion": ["得分王", "Scoring Champion"],
  "All-NBA": ["最佳阵容", "All-NBA"],
  "All-Defensive Team": ["最佳防守阵容", "All-Defensive"],
  "All-Rookie Team": ["最佳新秀阵容", "All-Rookie"],
  "NBA All-Star": ["全明星", "All-Star"],
  "NBA All-Star Most Valuable Player": ["全明星 MVP", "All-Star MVP"],
  "NBA Cup Most Valuable Player": ["季中赛 MVP", "NBA Cup MVP"],
  "NBA Cup All-Tournament Team": ["季中赛最佳阵容", "NBA Cup All-Tournament"],
  "Olympic Gold Medal": ["奥运金牌", "Olympic gold"],
  "Olympic Silver Medal": ["奥运银牌", "Olympic silver"],
  "Olympic Bronze Medal": ["奥运铜牌", "Olympic bronze"],
  "NBA Player of the Month": ["月最佳球员", "Player of the Month"],
  "NBA Player of the Week": ["周最佳球员", "Player of the Week"],
  "NBA Rookie of the Month": ["月最佳新秀", "Rookie of the Month"],
};
const ORDER = Object.keys(AWARDS);
const MAJOR = new Set(ORDER.slice(0, 8));
const rank = (a: string) => { const i = ORDER.indexOf(a); return i < 0 ? ORDER.length : i; };
// Weekly and monthly awards run to dozens, so they show as a count only.
// Only these split by team number; elsewhere the feed's number means nothing.
const TEAMED = new Set(["All-NBA", "All-Defensive Team", "All-Rookie Team"]);
const COUNT_ONLY = new Set(["NBA Player of the Week", "NBA Player of the Month", "NBA Rookie of the Month"]);

function HonorCard({ title, count, detail, major }: { title: string; count: number; detail?: string; major: boolean }) {
  return (
    <div className="panel" style={{ margin: 0, padding: "10px 14px", minWidth: 140, background: major ? "var(--pop-yellow)" : "var(--panel)", color: major ? "var(--on-yellow)" : undefined }}>
      <div style={{ fontFamily: "var(--font-display)", fontSize: 30, lineHeight: 1 }}>×{count}</div>
      <div style={{ fontWeight: 700, marginTop: 4 }}>{title}</div>
      {detail && <div className="note" style={{ color: "inherit", opacity: 0.8, marginTop: 4, maxWidth: 260 }}>{detail}</div>}
    </div>
  );
}

/** Season label "2012-13" → "12-13" so a long run of seasons stays short. */
const short = (s: string) => s.slice(2);

export function PlayerHonors({ id }: { id: number }) {
  const { t, lang } = useLang();
  const q = usePlayerHonors(id);
  const rows = q.data ?? [];
  if (rows.length === 0) return null;
  const li = lang === "zh" ? 0 : 1;
  const nameOf = (a: string) => AWARDS[a]?.[li] ?? a;
  // All-NBA and its kin split by team number; group them back into one card with the number in the detail.
  const byAward = new Map<string, PlayerHonor[]>();
  for (const r of rows.filter((x) => !x.award.includes("Sporting News"))) byAward.set(r.award, [...(byAward.get(r.award) ?? []), r]);
  const cards = [...byAward.entries()].sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0])).map(([award, parts]) => {
    const seasons = parts.flatMap((p) => p.seasons).sort();
    const n = parts.reduce((s, p) => s + p.n, 0);
    let detail: string | undefined;
    if (TEAMED.has(award) && parts.length > 1) {
      detail = parts.filter((p) => p.team).map((p) => t("{k} 阵 ×{n}", { k: p.team ?? "", n: p.n })).join(" · ");
    } else if (!COUNT_ONLY.has(award) && seasons.length) {
      detail = seasons.map(short).join(", ");
    }
    return <HonorCard key={award} title={nameOf(award)} count={n} detail={detail} major={MAJOR.has(award)} />;
  });
  return (
    <section className="panel">
      <span className="caption">{t("荣誉")}</span>
      <div className="row" style={{ gap: 12, marginTop: 14, alignItems: "stretch" }}>{cards}</div>
      <p className="note" style={{ marginTop: 10 }}>{t("来源 stats.nba.com；赛季以 {ex} 这样的简写显示。", { ex: "12-13" })}</p>
    </section>
  );
}

function Years({ rows }: { rows: TeamHonorRow[] }) {
  return <>{rows.map((r) => r.year).filter((y): y is number => y != null).sort((a, b) => b - a).join(", ")}</>;
}

export function TeamHonors({ team }: { team: string }) {
  const { t, lang } = useLang();
  const q = useTeamHonors(team);
  const h = q.data;
  if (!h || Object.values(h).every((v) => v.length === 0)) return null;
  const finals = [...h.champion].sort((a, b) => (b.year ?? 0) - (a.year ?? 0));
  return (
    <section className="panel">
      <span className="caption">{t("球队荣誉")}</span>
      <div className="row" style={{ gap: 12, marginTop: 14, alignItems: "stretch" }}>
        {h.champion.length > 0 && <HonorCard title={t("总冠军")} count={h.champion.length} detail={finals.map((r) => r.year).join(", ")} major />}
        {h.conference.length > 0 && <HonorCard title={t("联盟冠军")} count={h.conference.length} detail={undefined} major={false} />}
        {h.division.length > 0 && <HonorCard title={t("分区冠军")} count={h.division.length} detail={undefined} major={false} />}
        {h.retired.length > 0 && <HonorCard title={t("退役球衣")} count={h.retired.length} detail={undefined} major={false} />}
        {h.hof.length > 0 && <HonorCard title={t("名人堂球员")} count={h.hof.length} detail={undefined} major={false} />}
      </div>
      {h.conference.length > 0 && <p style={{ marginTop: 10 }}><b>{t("联盟冠军")}：</b><Years rows={h.conference} /></p>}
      {h.retired.length > 0 && (
        <p style={{ marginTop: 10 }}><b>{t("退役球衣")}：</b>{h.retired.map((r, i) => (
          <span key={`${r.player_id}-${i}`}>{i > 0 && " · "}{r.jersey ? `#${r.jersey} ` : ""}{r.player_id ? <Link to={`/players/${r.player_id}`}>{r.player}</Link> : r.player}</span>
        ))}</p>
      )}
      {h.hof.length > 0 && (
        <p style={{ marginTop: 10 }}><b>{t("名人堂球员")}：</b>{h.hof.map((r, i) => (
          <span key={`${r.player_id}-${i}`}>{i > 0 && " · "}{r.player_id ? <Link to={`/players/${r.player_id}`}>{r.player}</Link> : r.player}</span>
        ))}</p>
      )}
      <p className="note" style={{ marginTop: 10 }}>{lang === "zh" ? "年份为赛季结束的年份。" : "Years are the season's closing year."}{" "}{t("来源 stats.nba.com。")}</p>
    </section>
  );
}
