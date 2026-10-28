import { useState } from "react";
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

/** Today's US Eastern date and the next two, as "YYYY-MM-DD" (the API groups games by Eastern date). */
function nextDays(n: number): string[] {
  const [y, m, d] = new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" }).split("-").map(Number);
  return Array.from({ length: n }, (_, i) => new Date(Date.UTC(y, m - 1, d + i)).toISOString().slice(0, 10));
}

function TeamSide({ team, score, lang }: { team: string; score: number | null; lang: "zh" | "en" }) {
  return (
    <span className="row" style={{ flex: 1, alignItems: "center", gap: 6 }}>
      <TeamLogo team={team} size={32} />
      <strong>{teamName(team, lang, true)}</strong>
      {score != null && <span className="num" style={{ marginLeft: "auto" }}>{score}</span>}
    </span>
  );
}

function Game({ g }: { g: ScheduledGame }) {
  const { t, lang } = useLang();
  const time = new Date(g.tipoff).toLocaleTimeString(lang === "zh" ? "zh-CN" : "en-US", { hour: "2-digit", minute: "2-digit" });
  return (
    <Link to={`/predict/${g.away_team}/${g.home_team}?date=${g.game_date}`} className="panel"
      style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", padding: "10px 14px", textDecoration: "none", color: "inherit", margin: 0 }}>
      <TeamSide team={g.away_team} score={g.completed ? g.away_score : null} lang={lang} />
      <span style={{ minWidth: 72, textAlign: "center" }}>{g.completed ? t("已结束") : time}{g.season_type === 3 ? ` · ${t("季后赛")}` : ""}</span>
      <TeamSide team={g.home_team} score={g.completed ? g.home_score : null} lang={lang} />
    </Link>
  );
}

export default function Predict() {
  const { t, lang } = useLang();
  usePageTitle(t("比赛预测"));
  const sched = useSchedule();
  const days = nextDays(3);
  const [pick, setPick] = useState(days[0]);
  const games = (sched.data ?? []).filter((g) => g.game_date === pick);
  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-red)", color: "#fff", borderColor: "#111" }}>
        <h1 style={{ fontSize: "var(--size-h1)" }}>{t("比赛预测")}</h1>
        <p style={{ margin: "6px 0 0" }}>{t("今天起三天的比赛。胜率和分差预测即将上线。")}</p>
      </section>
      <div className="seg seg-lg" role="group" aria-label={t("日期")}>
        {days.map((d) => (
          <button key={d} type="button" aria-pressed={pick === d} onClick={() => setPick(d)}>
            {dayLabel(d, lang)}{d === days[0] ? ` · ${t("今天")}` : ""}
          </button>
        ))}
      </div>
      {sched.isLoading ? <Loading what={t("赛程")} /> : sched.error ? <Failed error={sched.error} /> : games.length === 0 ? (
        <p>{t("这一天没有比赛。")}</p>
      ) : (
        <section style={{ display: "grid", gap: 10 }}>
          <h2><small>{t("{n} 场", { n: games.length })}</small></h2>
          {games.map((g) => <Game key={g.game_id} g={g} />)}
        </section>
      )}
    </>
  );
}
