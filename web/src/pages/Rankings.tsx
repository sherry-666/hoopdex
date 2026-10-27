import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Rankings as RankingsData, Standing, useRankings, useRankingSeasons } from "../api";
import { Failed, Loading, SeasonSelect } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";
import { OvrBadge } from "../components/rating";
import { teamName } from "../teams";

// The play-in tournament started in 2020-21: seeds 7-10 play in, otherwise 1-8 make the playoffs.
const hasPlayIn = (season: string) => season >= "2020-21";
// ESPN's clinch codes next to a team: what it has secured so far (final standings keep the last one).
const CLINCH: Record<string, string> = { "*": "联盟最佳战绩", z: "本区第一", y: "分区冠军", x: "晋级季后赛", xp: "晋级季后赛（经附加赛）",
  pb: "晋级附加赛", e: "无缘季后赛", o: "无缘季后赛" };

function StandingsTable({ title, rows, season }: { title: string; rows: Standing[]; season: string }) {
  const { t, lang } = useLang();
  const cut = hasPlayIn(season) ? 6 : 8;
  return (
    <section className="panel">
      <span className="caption">{title}</span>
      <div className="table-box" style={{ marginTop: 12, maxHeight: "none" }}>
        <table className="data">
          <thead>
            <tr>
              <th className="num-col">#</th><th>{t("球队")}</th><th className="num-col">{t("胜")}</th><th className="num-col">{t("负")}</th>
              <th className="num-col">{t("胜率")}</th><th className="num-col hide-narrow">{t("胜场差")}</th>
              <th className="num-col hide-narrow">{t("近10场")}</th><th className="num-col hide-narrow">{t("连续")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.team} style={r.rank === cut + 1 ? { borderTop: "3px solid var(--ink)" } : r.rank === 11 && hasPlayIn(season) ? { borderTop: "2px dashed var(--ink)" } : undefined}>
                <td className="num-col">{r.rank}</td>
                <td>
                  {teamName(r.team, lang, true)}
                  {r.clincher && CLINCH[r.clincher] && <span className="tag" style={{ marginLeft: 6 }}>{t(CLINCH[r.clincher])}</span>}
                </td>
                <td className="num-col">{r.wins}</td><td className="num-col">{r.losses}</td>
                <td className="num-col">{r.win_pct == null ? "—" : r.win_pct.toFixed(3).replace(/^0/, "")}</td>
                <td className="num-col hide-narrow">{r.games_behind ? r.games_behind : "—"}</td>
                <td className="num-col hide-narrow">{r.last10 ?? "—"}</td><td className="num-col hide-narrow">{r.streak ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// Stat leaders come from the API per category; the three ratings are re-sorts of the rated players.
const STATS: { key: string; title: string; pct?: boolean }[] = [
  { key: "pts", title: "得分" }, { key: "reb", title: "篮板" }, { key: "ast", title: "助攻" }, { key: "stl", title: "抢断" },
  { key: "blk", title: "盖帽" }, { key: "fg3m", title: "三分命中" }, { key: "fg_pct", title: "投篮%", pct: true },
  { key: "fg3_pct", title: "三分%", pct: true }, { key: "ft_pct", title: "罚球%", pct: true },
];
type Rating = "ovr" | "off" | "def";
const RATINGS: Record<Rating, string> = { ovr: "综合评分", off: "进攻评分", def: "防守评分" };

function PlayerRanks({ data, season }: { data: RankingsData; season: string }) {
  const { t, lang } = useLang();
  const [key, setKey] = useState("pts");
  const rating = key in RATINGS ? (key as Rating) : null;
  const stat = STATS.find((s) => s.key === key);
  const rows = useMemo(() => {
    if (rating) {
      return [...data.players].sort((a, b) => ((b[rating] ?? -1) - (a[rating] ?? -1)) || b.minutes - a.minutes)
        .map((p) => ({ player_id: p.player_id, name: p.name, team: p.team, gp: p.gp, value: p[rating] ?? 0 }));
    }
    return data.leaders[key] ?? [];
  }, [data, key, rating]);
  const fmt = (v: number) => (stat?.pct ? `${(v * 100).toFixed(1)}%` : v.toFixed(1));
  return (
    <section className="panel">
      <span className="caption">{t("球员排名")}</span>
      <div className="panel-head">
        <p className="note">
          {rating
            ? (data.players_early ? t("赛季刚开始，评分是本赛季与上赛季的合成值；上场不满 60 分钟的球员不参与。")
              : t("{season} 赛季满 500 分钟的球员，按评分排序。", { season }))
            : stat?.pct ? t("{season} 赛季常规赛；命中数要达到球队每场平均的门槛才入榜。", { season })
              : t("{season} 赛季常规赛场均数据；至少打了球队 70% 的比赛（{n} 场）。", { season, n: Math.ceil(data.team_games * 0.7) })}
        </p>
      </div>
      <div className="seg" role="group" aria-label={t("排序")} style={{ flexWrap: "wrap", marginBottom: 12 }}>
        {STATS.map((s) => <button key={s.key} type="button" aria-pressed={key === s.key} onClick={() => setKey(s.key)}>{t(s.title)}</button>)}
        {(Object.keys(RATINGS) as Rating[]).map((k) => <button key={k} type="button" aria-pressed={key === k} onClick={() => setKey(k)}>{t(RATINGS[k])}</button>)}
      </div>
      {rows.length === 0 && <p className="note">{t("这个赛季还没有这项数据。")}</p>}
      {rows.length > 0 && (
        <div className="table-box" style={{ maxHeight: "none" }}>
          <table className="data">
            <thead>
              <tr>
                <th className="num-col">#</th><th>{t("姓名")}</th><th>{t("球队")}</th>
                <th className="num-col">{t(stat?.title ?? RATINGS[rating!])}</th><th className="num-col hide-narrow">{t("场次")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p, i) => (
                <tr key={p.player_id}>
                  <td className="num-col">{i + 1}</td>
                  <td><Link to={`/players/${p.player_id}?season=${season}`}>{p.name}</Link></td>
                  <td>{teamName(p.team, lang, true)}</td>
                  <td className="num-col">{rating ? <OvrBadge ovr={p.value} size={30} /> : <b>{fmt(p.value)}</b>}</td>
                  <td className="num-col hide-narrow">{p.gp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function Rankings() {
  const { t, lang } = useLang();
  usePageTitle(t("排名"));
  const seasons = useRankingSeasons();
  const [params, setParams] = useSearchParams();
  const season = params.get("season") ?? seasons.data?.[0];
  const q = useRankings(season);
  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-yellow)", color: "var(--on-yellow)", borderColor: "#111" }}>
        <h1 style={{ fontSize: "var(--size-h1)" }}>{t("排名")}</h1>
        <p style={{ margin: "6px 0 0" }}>{t("{season} 赛季东西部排名和球员数据排行。", { season: season ?? "" })}</p>
      </section>
      <div className="row">
        <SeasonSelect value={season} seasons={seasons.data} onChange={(s) => setParams({ season: s }, { replace: true })} />
        {q.data && <span className="note">{t("每天自动更新，来源 ESPN，{date} 更新。", { date: new Date(q.data.updated_at).toLocaleDateString(lang === "zh" ? "zh-CN" : "en-US") })}</span>}
      </div>
      {(q.isLoading || seasons.isLoading) && <Loading what="排名" />}
      {q.error && <Failed error={q.error} />}
      {q.data && season && (
        <>
          <div className="grid">
            <StandingsTable title={t("东部")} rows={q.data.east} season={season} />
            <StandingsTable title={t("西部")} rows={q.data.west} season={season} />
          </div>
          <PlayerRanks data={q.data} season={season} />
        </>
      )}
    </>
  );
}
