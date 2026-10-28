import { Link } from "react-router-dom";
import { ScheduledGame, useSchedule } from "../api";
import { Failed, Loading, TeamLogo } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";
import { teamName } from "../teams";

/** "2026-10-28" as a weekday and date; parsed as a calendar date so the time zone cannot shift it. */
function dayLabel(iso: string, lang: "zh" | "en") {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(lang === "zh" ? "zh-CN" : "en-US", { month: "long", day: "numeric", weekday: "long" });
}

function TeamSide({ team, score, lang }: { team: string; score: number | null; lang: "zh" | "en" }) {
  return (
    <Link to={`/teams/${team}`} className="row" style={{ flex: 1, alignItems: "center", gap: 6, textDecoration: "none", color: "inherit" }}>
      <TeamLogo team={team} size={32} />
      <strong>{teamName(team, lang)}</strong>
      {score != null && <span className="num" style={{ marginLeft: "auto" }}>{score}</span>}
    </Link>
  );
}

function Game({ g }: { g: ScheduledGame }) {
  const { t, lang } = useLang();
  const time = new Date(g.tipoff).toLocaleTimeString(lang === "zh" ? "zh-CN" : "en-US", { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="panel" style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", padding: "10px 14px" }}>
      <TeamSide team={g.away_team} score={g.completed ? g.away_score : null} lang={lang} />
      <span style={{ minWidth: 72, textAlign: "center" }}>{g.completed ? t("已结束") : time}{g.season_type === 3 ? ` · ${t("季后赛")}` : ""}</span>
      <TeamSide team={g.home_team} score={g.completed ? g.home_score : null} lang={lang} />
    </div>
  );
}

export default function Predict() {
  const { t, lang } = useLang();
  usePageTitle(t("比赛预测"));
  const sched = useSchedule();
  const days = new Map<string, ScheduledGame[]>();
  for (const g of sched.data ?? []) days.set(g.game_date, [...(days.get(g.game_date) ?? []), g]);
  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-red)", color: "#fff", borderColor: "#111" }}>
        <h1 style={{ fontSize: "var(--size-h1)" }}>{t("比赛预测")}</h1>
        <p style={{ margin: "6px 0 0" }}>{t("今天起三天的比赛。胜率和分差预测即将上线。")}</p>
      </section>
      {sched.isLoading ? <Loading what={t("赛程")} /> : sched.error ? <Failed error={sched.error} /> : days.size === 0 ? (
        <p>{t("这几天没有比赛。")}</p>
      ) : [...days].map(([day, games]) => (
        <section key={day} style={{ display: "grid", gap: 10 }}>
          <h2>{dayLabel(day, lang)} <small>{t("{n} 场", { n: games.length })}</small></h2>
          {games.map((g) => <Game key={g.game_id} g={g} />)}
        </section>
      ))}
    </>
  );
}
