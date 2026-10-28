import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { HallRow, useCareerTop, useDefaultSeason, useHallOfFame, usePlayers } from "../api";
import { Failed, Loading, PlayerCard } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";

const ISSUES = [
  { to: "/roles", no: "#1", title: "定位实验室", line: "7 种进攻原型、4 种防守原型，看每名球员是哪几种的混合。", tone: "var(--pop-yellow)", ink: "var(--on-yellow)" },
  { to: "/players", no: "#2", title: "球员名册", line: "每名球员一张卡：超能力、战力数值、风格构成。", tone: "var(--pop-blue)", ink: "var(--on-blue)" },
  { to: "/predict", no: "#3", title: "比赛预测", line: "按上场球员算两队实力，给出胜率和分差。即将登场。", tone: "var(--pop-red)", ink: "var(--on-red)" },
];

function Honors({ p }: { p: HallRow }) {
  const { t } = useLang();
  return (
    <div className="row" style={{ gap: 6, fontSize: 13 }}>
      <span className="tag">{t("冠军")} {p.titles}</span>
      <span className="tag">MVP {p.mvps}</span>
      <span className="tag">{t("全明星")} {p.all_stars}</span>
    </div>
  );
}

export default function Home() {
  const season = useDefaultSeason();
  const players = usePlayers(season);
  const careerTop = useCareerTop("career");
  const hof = useHallOfFame();
  const navigate = useNavigate();
  const { t } = useLang();
  usePageTitle();
  const [q, setQ] = useState("");
  // Regular players only: 500+ minutes, or early in a season 40% of the minutes leader's.
  const sections = useMemo(() => {
    const all = players.data ?? [];
    const floor = Math.min(500, 0.4 * Math.max(0, ...all.map((p) => p.minutes)));
    const regular = all.filter((p) => p.minutes >= floor);
    const top = (key: "ovr" | "off" | "def") =>
      regular.filter((p) => p[key] != null).sort((a, b) => (b[key] ?? 0) - (a[key] ?? 0)).slice(0, 6);
    return [
      { title: "生涯最强球员", note: "（生涯总评）", list: careerTop.data ?? [], career: true },
      { title: "名人堂", note: "（荣誉与能力 · 生涯总评）", list: hof.data ?? [], career: true },
      { title: "赛季最佳球员", note: "（{season} · 总评）", list: top("ovr") },
      { title: "赛季最佳进攻球员", note: "（{season} · 进攻评分）", list: top("off") },
      { title: "赛季最佳防守球员", note: "（{season} · 防守评分）", list: top("def") },
    ];
  }, [players.data, careerTop.data, hof.data]);

  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-yellow)", color: "var(--on-yellow)", borderColor: "#111", padding: "28px 24px" }}>
        <h1 style={{ fontFamily: "var(--font-latin)", fontSize: "clamp(40px, 7vw, 76px)", lineHeight: 0.95, letterSpacing: 1.5, color: "var(--pop-red)", WebkitTextStroke: "2px #111", paintOrder: "stroke fill" }}>
          KNOW THE GAME
        </h1>
        <p style={{ maxWidth: "60ch", margin: "12px 0 18px" }}>
          {t("Hoopedia 用逐回合数据、追踪数据和战术类型，把每个人的打法拆成几种纯粹原型，再把最突出的那几项变成超能力。所有数字都能追到来源。")}
        </p>
        <form onSubmit={(e) => { e.preventDefault(); navigate(q ? `/players?q=${encodeURIComponent(q)}` : "/players"); }} className="row">
          <input className="search" type="search" placeholder={t("找一位球员：Kawhi Leonard")} aria-label={t("搜索球员")} value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="submit" className="btn primary" style={{ background: "var(--pop-red)", color: "#fff", fontSize: 16, padding: "8px 18px" }}>{t("搜索")}</button>
        </form>
      </section>

      <div style={{ display: "grid", gap: 24, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 15rem), 1fr))" }}>
        {ISSUES.map((i) => (
          <Link key={i.to} to={i.to} className="panel" style={{ background: i.tone, color: i.ink, borderColor: "#111", textDecoration: "none" }}>
            <div style={{ fontFamily: "var(--font-latin)", fontSize: 40, lineHeight: 1 }}>{i.no}</div>
            <h2 style={{ fontSize: "var(--size-h2)" }}>{t(i.title)}</h2>
            <p style={{ margin: "6px 0 0" }}>{t(i.line)}</p>
          </Link>
        ))}
      </div>

      {players.isLoading && <Loading what="球员" />}
      {players.error && <Failed error={players.error} />}
      {sections.map((sec) => (
        <section key={sec.title}>
          <h2 style={{ fontSize: "var(--size-h2)", marginBottom: 14 }}>
            {t(sec.title)} <span className="note">{t(sec.note, { season: season ?? "" })}</span>
          </h2>
          <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))" }}>
            {sec.list.map((p) => <PlayerCard key={p.player_id} id={p.player_id} name={p.name} team={p.team} style={p.off_style} archetype={p.off_top} season={"career" in sec ? undefined : season} ovr={p.ovr}
              off={"titles" in p ? undefined : p.off} def={"titles" in p ? undefined : p.def}
              extra={"titles" in p ? <Honors p={p as HallRow} /> : undefined} />)}
          </div>
        </section>
      ))}
    </>
  );
}
