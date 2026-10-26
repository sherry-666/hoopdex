import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CAREER, Side, SIDE_LABEL, seriesColor, useRoleView, useSeason, useSeasons } from "../api";
import { ClusterView, ProfileHeatmap, StyleMap } from "../components/charts";
import { Failed, Loading } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";

export default function RolesLab() {
  const defaultSeason = useSeason();
  const seasons = useSeasons();
  const [params, setParams] = useSearchParams();
  const season = params.get("season") ?? defaultSeason;
  const isCareer = season === CAREER;
  const info = seasons.data?.find((s) => s.season === season);
  const early = !!info && info.qualified === 0;   // nobody has 500 minutes yet: show everyone
  const { t, name } = useLang();
  usePageTitle(t("定位实验室"));
  const [side, setSide] = useState<Side>("offense");
  const [pick, setPick] = useState<number | null>(null);
  const navigate = useNavigate();
  const view = useRoleView(season, side);
  const onPick = useCallback((id: number | null) => setPick(id), []);
  const onOpen = useCallback((id: number) => navigate(`/players/${id}`), [navigate]);

  const members = useMemo(() => {
    if (!view.data || pick == null) return [];
    return view.data.players.filter((p) => (p.in_fit || early) && (p.weights[String(pick)] ?? 0) >= 0.4)
      .sort((a, b) => (b.weights[String(pick)] ?? 0) - (a.weights[String(pick)] ?? 0)).slice(0, 12);
  }, [view.data, pick, early]);
  const pickName = name(view.data?.archetypes.find((a) => a.type_id === pick)?.name);

  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-yellow)", color: "var(--on-yellow)", borderColor: "#111" }}>
        <h1 style={{ fontSize: "var(--size-h1)" }}>{t("定位实验室")}</h1>
        <p style={{ margin: "6px 0 0", maxWidth: "62ch" }}>
          {t("每名球员的打法是几种「纯粹原型」的混合。先选进攻或防守，再点一个原型，看谁最接近它。")}{" "}
          {season && (isCareer ? t("生涯视图：每名球员各赛季的打法按上场分钟加权平均，至少有一季满 500 分钟才算核心样本。")
            : t("数据：{season} 常规赛，满 500 分钟的球员。", { season }))}
        </p>
      </section>
      {early && <p className="bubble" style={{ margin: 0 }}>{t("本赛季刚开始，还没有球员满 500 分钟：下面显示全部球员。定位是本赛季和上赛季的过渡值，图上的位置只用本赛季数据，可信度低。")}</p>}

      <div className="row">
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("赛季")}
          <select className="select" value={season ?? ""} onChange={(e) => { setParams({ season: e.target.value }, { replace: true }); setPick(null); }}>
            <option value={CAREER}>{t("生涯")}</option>
            {seasons.data?.filter((s) => s.has_views).map((s) => (
              <option key={s.season} value={s.season}>{s.in_progress ? t("{season}（进行中）", { season: s.season }) : s.season}</option>
            ))}
          </select>
        </label>
        <div className="seg" role="group" aria-label={t("进攻或防守")}>
          {(["offense", "defense"] as Side[]).map((s) => (
            <button key={s} type="button" aria-pressed={side === s} onClick={() => { setSide(s); setPick(null); }}>{t(SIDE_LABEL[s])}</button>
          ))}
        </div>
        {view.data?.archetypes.map((a) => (
          <button key={a.type_id} type="button" className="chip" aria-pressed={pick === a.type_id}
            onClick={() => setPick(pick === a.type_id ? null : a.type_id)}>
            <span className="swatch" style={{ background: seriesColor(a.type_id) }} />{name(a.name)}
            <span style={{ color: "var(--muted)" }}>{early ? view.data!.players.filter((p) => p.top_archetype_id === a.type_id).length : a.n_fit}</span>
          </button>
        ))}
      </div>

      {view.isLoading && <Loading what="定位模型" />}
      {view.error && <Failed error={view.error} />}
      {view.data && (
        <>
          <section className="panel">
            <span className="caption">{t("聚类视图")}</span>
            <div className="panel-head">
              <p className="note">{t("坐标轴是由全部打法特征合成的综合指数，方向选的是让原型分得最开。3D 可以拖动旋转，点一个点打开他的球员档案。")}</p>
            </div>
            <ClusterView players={view.data.players} axes={view.data.axes} archetypes={view.data.archetypes}
              pick={pick} onPick={onPick} onOpen={onOpen} includeLow={early} />
          </section>

          {pick != null && (
            <section className="panel pop-in">
              <span className="caption">{t("最接近「{name}」的球员", { name: pickName })}</span>
              <div className="row" style={{ marginTop: 12 }}>
                {members.length === 0 && <p className="note">{t("没有球员在这个原型上占比超过 40%。")}</p>}
                {members.map((p) => (
                  <Link key={p.player_id} to={`/players/${p.player_id}`} className="chip">
                    {p.name}<span style={{ color: "var(--muted)" }}>{Math.round((p.weights[String(pick)] ?? 0) * 100)}%</span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <section className="panel">
              <span className="caption">{t("风格地图")}</span>
              <p className="note" style={{ margin: "8px 0" }}>{t("点的颜色是主原型，越淡越混合。两条轴没有含义，只看远近。")}</p>
              <StyleMap players={view.data.players} archetypes={view.data.archetypes} pick={pick} onPick={onPick} onOpen={onOpen} includeLow={early} />
            </section>
            <section className="panel">
              <span className="caption">{t("原型画像")}</span>
              <p className="note" style={{ margin: "8px 0" }}>{t("原型是最极端的纯粹打法，所以数值比大类更夸张。单位是相对联盟平均的标准差。")}</p>
              <ProfileHeatmap side={side} archetypes={view.data.archetypes} families={view.data.families} pick={pick} onPick={onPick} />
            </section>
          </div>
        </>
      )}
    </>
  );
}
