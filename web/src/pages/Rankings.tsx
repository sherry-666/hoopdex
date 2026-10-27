import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { RankedPlayer, Standing, useRankings, useRankingSeasons } from "../api";
import { Failed, Loading, SeasonSelect } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";
import { OffDef, OvrBadge } from "../components/rating";
import { teamName } from "../teams";

// The play-in tournament started in 2020-21: seeds 7-10 play in, otherwise 1-8 make the playoffs.
const hasPlayIn = (season: string) => season >= "2020-21";
const CLINCH: Record<string, string> = { z: "最佳战绩", y: "分区第一", x: "锁定季后赛", e: "无缘季后赛", o: "已淘汰" };

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
                  {r.clincher && CLINCH[r.clincher] && <span className="tag" style={{ marginLeft: 6 }} title={t(CLINCH[r.clincher])}>{r.clincher}</span>}
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

type Sort = "ovr" | "off" | "def";
const SORTS: Record<Sort, string> = { ovr: "综合", off: "进攻", def: "防守" };

function PlayerRanks({ players, early, season }: { players: RankedPlayer[]; early: boolean; season: string }) {
  const { t, lang } = useLang();
  const [sort, setSort] = useState<Sort>("ovr");
  const rows = useMemo(() => [...players].sort((a, b) => ((b[sort] ?? -1) - (a[sort] ?? -1)) || b.minutes - a.minutes), [players, sort]);
  return (
    <section className="panel">
      <span className="caption">{t("球员排名")}</span>
      <div className="panel-head">
        <p className="note">{early ? t("赛季刚开始，评分是本赛季与上赛季的合成值；上场不满 60 分钟的球员不参与。") : t("{season} 赛季满 500 分钟的球员，按评分排序。", { season })}</p>
        <div className="seg" role="group" aria-label={t("排序")}>
          {(Object.keys(SORTS) as Sort[]).map((k) => (
            <button key={k} type="button" aria-pressed={sort === k} onClick={() => setSort(k)}>{t(SORTS[k])}</button>
          ))}
        </div>
      </div>
      <div className="table-box" style={{ maxHeight: "none" }}>
        <table className="data">
          <thead>
            <tr>
              <th className="num-col">#</th><th>{t("姓名")}</th><th>{t("球队")}</th><th className="num-col">OVR</th><th>{t("攻 / 守")}</th>
              <th className="num-col hide-narrow">{t("场次")}</th><th className="num-col hide-narrow">{t("分钟")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p, i) => (
              <tr key={p.player_id}>
                <td className="num-col">{i + 1}</td>
                <td><Link to={`/players/${p.player_id}?season=${season}`}>{p.name}</Link></td>
                <td>{teamName(p.team, lang, true)}</td>
                <td className="num-col"><OvrBadge ovr={p.ovr} size={30} /></td>
                <td><OffDef off={p.off} def={p.def} size={13} /></td>
                <td className="num-col hide-narrow">{p.gp}</td><td className="num-col hide-narrow">{Math.round(p.minutes).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
        <p style={{ margin: "6px 0 0" }}>{t("{season} 赛季东西部排名和球员评分排名。", { season: season ?? "" })}</p>
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
          <PlayerRanks players={q.data.players} early={q.data.players_early} season={season} />
        </>
      )}
    </>
  );
}
