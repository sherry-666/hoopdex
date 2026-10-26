import { useState } from "react";
import { Link } from "react-router-dom";
import { seriesColor, TeamProfile, useTeams } from "../api";
import { Failed, Loading, MixBar } from "../components/comic";
import { OffDef, OvrBadge } from "../components/rating";
import { useLang } from "../i18n";
import { teamName } from "../teams";

function mixFrom(shares: Record<string, number>, order: string[]) {
  return order.map((name, id) => ({ id, name, weight: shares[name] ?? 0 }));
}

function TeamCard({ t, season, archetypes }: { t: TeamProfile; season: string; archetypes: { offense: string[]; defense: string[] } }) {
  const { t: tr, name, lang } = useLang();
  const off = mixFrom(t.off_mix, archetypes.offense);
  const top = [...off].sort((a, b) => b.weight - a.weight).slice(0, 3);
  return (
    <article className="panel pop-in" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
        <div style={{ minWidth: 0 }}>
          <h3 style={{ fontSize: 24, lineHeight: 1.1 }}>{teamName(t.team, lang, lang === "en")}</h3>
          <span className="tag" style={{ marginTop: 6 }}>{name(t.defense_tag)}</span>
        </div>
        <div style={{ textAlign: "center", display: "grid", justifyItems: "center", gap: 4 }}>
          <OvrBadge ovr={t.ovr} size={52} />
          <div className="note">{tr("球队评分")}</div>
        </div>
      </div>
      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <OffDef off={t.off} def={t.def} size={16} />
        {t.ortg != null && t.drtg != null && (
          <span className="note" title={tr("每 100 回合得分 / 失分")}>
            {tr("得 {o} · 失 {d} / 百回合", { o: t.ortg.toFixed(1), d: t.drtg.toFixed(1) })}
          </span>
        )}
      </div>
      <div>
        <div className="note">{tr("进攻")}</div>
        <MixBar mix={off} height={16} />
        <div className="row" style={{ gap: 10, marginTop: 4 }}>
          {top.map((m) => (
            <span key={m.id} className="row" style={{ gap: 4, fontSize: "var(--size-caption)" }}>
              <span className="swatch" style={{ background: seriesColor(m.id) }} />{name(m.name)} {Math.round(m.weight * 100)}%
            </span>
          ))}
        </div>
      </div>
      <div>
        <div className="note">{tr("防守")}</div>
        <MixBar mix={mixFrom(t.def_mix, archetypes.defense)} height={12} />
      </div>
      <div>
        <div className="note" style={{ marginBottom: 4 }}>{tr("主力轮换")}</div>
        <ol style={{ margin: 0, paddingLeft: "1.2em", display: "grid", gap: 2 }}>
          {t.core.slice(0, 6).map((p) => (
            <li key={p.player_id} style={{ fontSize: "var(--size-caption)" }}>
              <Link to={`/players/${p.player_id}?season=${season}`}>{p.name}</Link>
              {p.ovr != null && <b> {p.ovr}</b>}
              {p.off != null && p.def != null && <span className="note"> ({tr("攻")}{p.off}/{tr("守")}{p.def})</span>}
              {p.style && <span className="note"> · {name(p.style)}</span>}
            </li>
          ))}
        </ol>
      </div>
    </article>
  );
}

export default function TeamsTab({ season, early }: { season: string | undefined; early: boolean }) {
  const { t, name } = useLang();
  const view = useTeams(season);
  const [style, setStyle] = useState<number | null>(null);
  if (view.isLoading || !season) return <Loading what="数据" />;
  if (view.error || !view.data) return <Failed error={view.error} />;
  const { styles, teams, archetypes } = view.data;
  const shown = styles.filter((s) => style == null || s.style_id === style);
  return (
    <>
      <p className="note" style={{ maxWidth: "80ch", margin: 0 }}>
        {t("按每队上场时间最多的 9 名球员，把他们的打法原型按分钟加权，得出球队的风格；再把风格相近的球队归成 5 种建队思路。打法是连续的，归类表示「最接近」，不是严格的派系。")}{" "}
        {t("交易过的球员算在他最后效力的球队。")}{" "}
        {t("球队评分（综合、进攻、防守）一半来自轮换球员的评分（按分钟加权），一半来自球队实际的每百回合净胜分、得分和失分，各自在当季 30 队里排名，80 分是联盟平均。")}
      </p>
      {early && <p className="bubble" style={{ margin: 0 }}>{t("本赛季刚开始，轮换和风格还会变化。")}</p>}
      <div className="row">
        <button type="button" className="chip" aria-pressed={style === null} onClick={() => setStyle(null)}>{t("全部")}</button>
        {styles.map((s) => (
          <button key={s.style_id} type="button" className="chip" aria-pressed={style === s.style_id}
            onClick={() => setStyle(style === s.style_id ? null : s.style_id)}>
            {name(s.name)} <span style={{ color: "var(--muted)" }}>{teams.filter((tm) => tm.style_id === s.style_id).length}</span>
          </button>
        ))}
      </div>
      {shown.map((s) => {
        const members = teams.filter((tm) => tm.style_id === s.style_id);
        if (!members.length) return null;
        return (
          <section key={s.style_id} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <span className="caption" style={{ fontSize: 20 }}>{name(s.name)}</span>
              <span className="note" style={{ marginLeft: 10 }}>{t("{n} 支球队", { n: members.length })}</span>
              {s.description && <p style={{ margin: "8px 0 0", maxWidth: "70ch" }}>{t(s.description)}</p>}
            </div>
            <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 270px), 1fr))" }}>
              {members.map((tm) => <TeamCard key={tm.team} t={tm} season={season} archetypes={archetypes} />)}
            </div>
          </section>
        );
      })}
    </>
  );
}
