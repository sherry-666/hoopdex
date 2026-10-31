import { Link } from "react-router-dom";
import { RecordGame, useRecord } from "../api";
import { Failed, Loading, TeamLogo } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";
import { teamName } from "../teams";

const pct = (v: number | null, digits = 0) => (v == null ? "–" : `${(v * 100).toFixed(digits)}%`);

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="panel" style={{ margin: 0, textAlign: "center", padding: "12px 10px" }}>
      <div style={{ fontFamily: "var(--font-display)", fontSize: 32 }} className="num">{value}</div>
      <div>{label}</div>
      {sub && <small>{sub}</small>}
    </div>
  );
}

function Row({ g }: { g: RecordGame }) {
  const { lang } = useLang();
  const side = (team: string, score: number, right: boolean) => (
    <span className="row" style={{ alignItems: "center", gap: 8, justifyContent: right ? "flex-start" : "flex-end" }}>
      {!right && <strong>{teamName(team, lang, true)}</strong>}
      <TeamLogo team={team} size={28} />
      {right && <strong>{teamName(team, lang, true)}</strong>}
      <span className="num" style={{ fontWeight: g.winner === team ? 700 : 400 }}>{score}</span>
    </span>
  );
  return (
    <Link to={`/predict/${g.game_id}`} className="panel"
      style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr auto", alignItems: "center", gap: 14, padding: "8px 14px", textDecoration: "none", color: "inherit", margin: 0 }}>
      {side(g.away, g.away_score, false)}
      <b>VS</b>
      {side(g.home, g.home_score, true)}
      <span className="tag num" style={{ background: g.correct ? "var(--pop-yellow)" : "transparent", color: g.correct ? "var(--on-yellow)" : "inherit", fontWeight: 700, minWidth: 92, textAlign: "center" }}>
        {g.correct ? "✓" : "✗"} {teamName(g.pick, lang, true)} {Math.round(g.pick_win * 100)}%
      </span>
    </Link>
  );
}

export default function PredictRecord() {
  const { t, lang } = useLang();
  usePageTitle(t("预测战绩"));
  const rec = useRecord();
  const days = new Map<string, RecordGame[]>();
  for (const g of rec.data?.games ?? []) days.set(g.game_date, [...(days.get(g.game_date) ?? []), g]);
  const dayLabel = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(lang === "zh" ? "zh-CN" : "en-US", { month: "long", day: "numeric", weekday: "long" });
  };
  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-red)", color: "#fff", borderColor: "#111" }}>
        <h1 style={{ fontSize: "var(--size-h1)" }}>{t("预测战绩")}</h1>
        <p style={{ margin: "6px 0 0" }}>
          {t("每天中午（美东）存下当天比赛的预测，打完后对照比分。")} <Link to="/predict" style={{ color: "inherit", fontWeight: 700 }}>← {t("比赛预测")}</Link>
        </p>
      </section>
      {rec.isLoading ? <Loading what={t("预测战绩")} /> : rec.error ? <Failed error={rec.error} /> : !rec.data || rec.data.all.games === 0 ? (
        <p>{t("还没有打完的预测。")}</p>
      ) : (
        <>
          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
            <Tile label={t("命中率")} value={pct(rec.data.all.correct / rec.data.all.games, 1)} sub={t("{c} / {n} 场", { c: rec.data.all.correct, n: rec.data.all.games })} />
            <Tile label={t("近 7 天")} value={rec.data.last7.games ? pct(rec.data.last7.correct / rec.data.last7.games, 1) : "–"} sub={t("{c} / {n} 场", { c: rec.data.last7.correct, n: rec.data.last7.games })} />
            <Tile label="Brier" value={rec.data.all.brier?.toFixed(3) ?? "–"} sub={t("越低越好；总猜 50% 是 0.250")} />
          </section>
          <section className="panel" style={{ margin: 0 }}>
            <h2>{t("预测胜率准不准")}</h2>
            <p style={{ margin: "0 0 8px" }}><small>{t("把预测会赢的一方按胜率分档，看实际赢了多少。两列越接近越准。")}</small></p>
            <table className="num" style={{ width: "100%" }}>
              <thead><tr><th style={{ textAlign: "left" }}>{t("预测胜率")}</th><th>{t("场数")}</th><th>{t("平均预测")}</th><th>{t("实际赢")}</th></tr></thead>
              <tbody>
                {rec.data.calibration.map((b) => (
                  <tr key={b.lo} style={{ textAlign: "center" }}>
                    <td style={{ textAlign: "left" }}>{Math.round(b.lo * 100)}%–{Math.round(b.hi * 100)}%</td>
                    <td>{b.games}</td><td>{pct(b.predicted)}</td><td>{pct(b.actual)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          {[...days.entries()].map(([d, gs]) => (
            <section key={d} style={{ display: "grid", gap: 10 }}>
              <h2>{dayLabel(d)} <small>{t("{c} / {n} 场命中", { c: gs.filter((g) => g.correct).length, n: gs.length })}</small></h2>
              {gs.map((g) => <Row key={g.game_id} g={g} />)}
            </section>
          ))}
        </>
      )}
    </>
  );
}
