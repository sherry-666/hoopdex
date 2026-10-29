import { useMemo, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useDefaultSeason, usePlayers, useSeasons } from "../api";
import { Failed, Loading, PlayerCard, SeasonSelect } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";
import { teamName } from "../teams";

type SortKey = "ovr" | "off" | "def" | "minutes" | "pts_36" | "ts_pct" | "usg_pct";
const SORTS: Record<SortKey, string> = { ovr: "综合评分", off: "进攻评分", def: "防守评分", minutes: "上场分钟", pts_36: "得分 / 36", ts_pct: "真实命中率", usg_pct: "使用率" };
const PAGE = 48;

export default function Roster() {
  const seasons = useSeasons();
  const defaultSeason = useDefaultSeason();
  const { t, name, lang } = useLang();
  usePageTitle(t("球员名册"));
  // Season, team and search live in the URL so a filtered list can be shared or bookmarked.
  const [params, setParams] = useSearchParams();
  const season = params.get("season") ?? defaultSeason;
  const team = params.get("team") ?? "";
  const query = params.get("q") ?? "";
  const players = usePlayers(season);
  const [family, setFamily] = useState<string | null>(null);
  const [defFamily, setDefFamily] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>("ovr");
  const [showLow, setShowLow] = useState(false);
  const [limit, setLimit] = useState(PAGE);

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
    setLimit(PAGE);
  };

  const info = seasons.data?.find((s) => s.season === season);
  const earlySeason = !!info && info.qualified === 0;   // nobody has 500 minutes yet
  const teams = useMemo(() => [...new Set((players.data ?? []).map((p) => p.team).filter(Boolean))]
    .sort((a, b) => teamName(a, lang, true).localeCompare(teamName(b, lang, true), lang === "zh" ? "zh-Hans-CN-u-co-pinyin" : "en")),
  [players.data, lang]);
  const families = useMemo(() => [...new Set((players.data ?? []).map((p) => p.off_family).filter(Boolean))] as string[], [players.data]);
  const defFamilies = useMemo(() => [...new Set((players.data ?? []).map((p) => p.def_family).filter(Boolean))] as string[], [players.data]);
  const rows = useMemo(() => {
    const ql = query.trim().toLowerCase();
    return (players.data ?? [])
      .filter((p) => (showLow || earlySeason || p.in_fit) && (!family || p.off_family === family) && (!defFamily || p.def_family === defFamily) && (!team || p.team === team)
        && (!ql || p.name.toLowerCase().includes(ql) || (p.team ?? "").toLowerCase().includes(ql)
          || teamName(p.team, "zh").includes(ql) || teamName(p.team, "en", true).toLowerCase().includes(ql)))
      .sort((a, b) => ((b[sort] ?? -1) as number) - ((a[sort] ?? -1) as number));
  }, [players.data, query, family, defFamily, team, sort, showLow, earlySeason]);

  // Teams used to be a tab here; old links go to their own page.
  if (params.get("tab") === "teams") return <Navigate to={`/teams${params.get("season") ? `?season=${params.get("season")}` : ""}`} replace />;

  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-blue)", color: "var(--on-blue)", borderColor: "#111" }}>
        <h1 style={{ fontSize: "var(--size-h1)" }}>{t("球员名册")}</h1>
        <p style={{ margin: "6px 0 0" }}>{t("{season} 赛季的全部球员。搜名字或球队，按进攻、防守大类筛选。", { season: season ?? "" })}</p>
      </section>
      <div className="row">
        <SeasonSelect value={season} seasons={seasons.data} onChange={(s) => setParam("season", s)} />
      </div>
      <div className="row">
        <input className="search" type="search" placeholder={t("Stephen Curry、DEN……")} aria-label={t("搜索球员或球队")} value={query}
          onChange={(e) => setParam("q", e.target.value)} />
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("球队")}
          <select className="select" value={team} onChange={(e) => setParam("team", e.target.value)}>
            <option value="">{t("全部球队")}</option>
            {teams.map((tm) => <option key={tm} value={tm}>{teamName(tm, lang, true)}</option>)}
          </select>
        </label>
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("进攻")}
          <select className="select" value={family ?? ""} onChange={(e) => setFamily(e.target.value || null)}>
            <option value="">{t("全部")}</option>
            {families.map((f) => <option key={f} value={f}>{name(f)}</option>)}
          </select>
        </label>
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("防守")}
          <select className="select" value={defFamily ?? ""} onChange={(e) => setDefFamily(e.target.value || null)}>
            <option value="">{t("全部")}</option>
            {defFamilies.map((f) => <option key={f} value={f}>{name(f)}</option>)}
          </select>
        </label>
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("排序")}
          <select className="select" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </select>
        </label>
        {!earlySeason && (
          <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>
            <input type="checkbox" checked={showLow} onChange={(e) => setShowLow(e.target.checked)} /> {t("包括不满 500 分钟的球员")}
          </label>
        )}
      </div>
      {earlySeason && <p className="bubble" style={{ margin: "0 0 12px" }}>{t("本赛季刚开始，还没有球员满 500 分钟：下面列出全部球员，定位和超能力都是低置信度的参考。")}</p>}
      <div className="row"><span className="note">{t("{n} 名球员", { n: rows.length })}</span></div>

      {(players.isLoading || !season) && <Loading what="名册" />}
      {players.error && <Failed error={players.error} />}
      <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))" }}>
        {rows.slice(0, limit).map((p) => (
          <PlayerCard key={p.player_id} id={p.player_id} name={p.name} team={p.team} style={p.off_style} archetype={p.off_top} season={season} ovr={p.ovr} off={p.off} def={p.def} />
        ))}
      </div>
      {rows.length > limit && (
        <div style={{ textAlign: "center" }}>
          <button type="button" className="btn primary" onClick={() => setLimit(limit + PAGE)}>{t("再看 {n} 位", { n: Math.min(PAGE, rows.length - limit) })}</button>
        </div>
      )}
    </>
  );
}
