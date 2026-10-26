import { useSearchParams } from "react-router-dom";
import { useDefaultSeason, useSeasons } from "../api";
import { SeasonSelect } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";
import TeamsTab from "./TeamsTab";

export default function Teams() {
  const seasons = useSeasons();
  const defaultSeason = useDefaultSeason();
  const { t } = useLang();
  usePageTitle(t("球队体系"));
  const [params, setParams] = useSearchParams();
  const withTeams = seasons.data?.filter((s) => s.has_teams);
  const season = params.get("season") ?? (withTeams?.some((s) => s.season === defaultSeason) ? defaultSeason : withTeams?.[0]?.season);
  const info = seasons.data?.find((s) => s.season === season);
  const setSeason = (s: string) => {
    const next = new URLSearchParams(params);
    next.set("season", s);
    setParams(next, { replace: true });
  };
  return (
    <>
      <section className="panel halftone" style={{ background: "var(--pop-red)", color: "#fff", borderColor: "#111" }}>
        <h1 style={{ fontSize: "var(--size-h1)" }}>{t("球队体系")}</h1>
        <p style={{ margin: "6px 0 0" }}>{t("{season} 赛季每支球队怎么打：进攻体系、球队评分和主力轮换。", { season: season ?? "" })}</p>
      </section>
      <div className="row">
        <SeasonSelect value={season} seasons={withTeams} onChange={setSeason} />
      </div>
      <TeamsTab season={season} early={!!info && info.qualified === 0} />
    </>
  );
}
