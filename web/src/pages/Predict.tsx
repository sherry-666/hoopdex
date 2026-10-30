import { useState } from "react";
import { Link } from "react-router-dom";
import { ScheduledGame, useSchedule } from "../api";
import { Failed, Loading, TeamLogo } from "../components/comic";
import { OvrBadge } from "../components/rating";
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

/** One side of a game row: [pct] logo name rating on the left, rating name logo [pct] on the right, so the names and
 *  ratings meet in the middle.
 *  The tag is the win probability of the favoured team, or the final score once the game is over. */
function TeamSide({ team, score, win, ovr, side, lang }: { team: string; score: number | null; win?: number; ovr: number | null; side: "left" | "right"; lang: "zh" | "en" }) {
  const tag = win != null
    ? <span className="tag num" style={{ background: "var(--pop-yellow)", color: "var(--on-yellow)", fontWeight: 700 }}>{Math.round(win * 100)}%</span>
    : score != null ? <span className="num">{score}</span> : null;
  const left = side === "left";
  return (
    <span className="row" style={{ alignItems: "center", gap: 8, justifyContent: left ? "flex-end" : "flex-start", minWidth: 0 }}>
      {left && tag}
      {left && <TeamLogo team={team} size={32} />}
      {!left && <OvrBadge ovr={ovr} size={28} />}
      <strong>{teamName(team, lang, true)}</strong>
      {left && <OvrBadge ovr={ovr} size={28} />}
      {!left && <TeamLogo team={team} size={32} />}
      {!left && tag}
    </span>
  );
}

function Game({ g }: { g: ScheduledGame }) {
  const { t, lang } = useLang();
  const time = new Date(g.tipoff).toLocaleTimeString(lang === "zh" ? "zh-CN" : "en-US", { hour: "2-digit", minute: "2-digit" });
  return (
    <Link to={`/predict/${g.away_team}/${g.home_team}?date=${g.game_date}`} className="panel"
      style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 16, padding: "10px 14px", textDecoration: "none", color: "inherit", margin: 0 }}>
      <TeamSide team={g.away_team} ovr={g.away_ovr} side="left" score={g.completed ? g.away_score : null} win={g.home_win != null && g.home_win < 0.5 ? 1 - g.home_win : undefined} lang={lang} />
      <span style={{ minWidth: 72, textAlign: "center", lineHeight: 1.2 }}>
        <b>VS</b><br /><small>{g.completed ? t("已结束") : time}{g.season_type === 3 ? ` · ${t("季后赛")}` : ""}</small>
      </span>
      <TeamSide team={g.home_team} ovr={g.home_ovr} side="right" score={g.completed ? g.home_score : null} win={g.home_win != null && g.home_win >= 0.5 ? g.home_win : undefined} lang={lang} />
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
        <p style={{ margin: "6px 0 0" }}>{t("今天起三天的比赛，标出预测会赢的一方和胜率。点进去看两队对比。")} <Link to="/predict/record" style={{ color: "inherit", fontWeight: 700 }}>{t("预测战绩")} →</Link></p>
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
