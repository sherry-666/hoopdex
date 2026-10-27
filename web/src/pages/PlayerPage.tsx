import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CareerLine, Injury, num, pct, Side, SIDE_LABEL, seriesColor, useCareer, useDefaultSeason, usePlayer, usePlayerSeasons, useRecentGames, useSeasons } from "../api";
import { Burst, TeamLink, Failed, Loading, MixBar, Portrait, PowerBubble, SeasonSelect } from "../components/comic";
import { useLang, usePageTitle } from "../i18n";
import { injuryWhere, label } from "../labels";
import { teamName } from "../teams";
import { OffDef, OvrBadge, RatingPanel } from "../components/rating";

const BURSTS: { key: string; title: string; fmt: (v: number) => string; tone: "red" | "yellow" | "blue" }[] = [
  { key: "pts_36", title: "得分 / 36", fmt: (v) => v.toFixed(1), tone: "red" },
  { key: "ts_pct", title: "真实命中率", fmt: (v) => `${(v * 100).toFixed(1)}%`, tone: "yellow" },
  { key: "usg_pct", title: "使用率", fmt: (v) => `${(v * 100).toFixed(1)}%`, tone: "blue" },
  { key: "ast_36", title: "助攻 / 36", fmt: (v) => v.toFixed(1), tone: "yellow" },
  { key: "reb_36", title: "篮板 / 36", fmt: (v) => v.toFixed(1), tone: "red" },
];
const MORE = ["fg3a_36", "fg3_pct", "drives_36", "touches_36", "shot_rim", "shot_long_mid", "cs_fga_share", "pullup_fga_share",
  "stl_36", "blk_36", "deflections_36", "height_cm", "weight_kg"];

export default function PlayerPage() {
  const { t, name, lang } = useLang();
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const allSeasons = useSeasons();
  const playerSeasons = usePlayerSeasons(id);
  const defaultSeason = useDefaultSeason();
  // ?season= wins; otherwise the default season if he played in it, else his latest one.
  const season = params.get("season")
    ?? (playerSeasons.data?.includes(defaultSeason ?? "") ? defaultSeason : playerSeasons.data?.[0]);
  const q = usePlayer(season, id);
  const career = useCareer(id);
  usePageTitle(q.data ? t("{name} 的打法原型与超能力 · NBA {season}", { name: q.data.name, season: season ?? "" }) : undefined);
  const seasonInfos = allSeasons.data?.filter((s) => playerSeasons.data?.includes(s.season));
  if (q.isLoading || !season) return <Loading what="球员档案" />;
  if (q.error || !q.data) return <Failed error={q.error ?? "没有这名球员"} />;
  const p = q.data;
  const off = p.roles.offense;
  const powers = [...p.powers.filter((x) => x.side === "offense"), ...p.powers.filter((x) => x.side === "defense")];

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <p className="note" style={{ margin: 0 }}><Link to={`/players?season=${season}`}>{t("← 球员名册")}</Link></p>
        <SeasonSelect value={season} seasons={seasonInfos} onChange={(s) => setParams({ season: s }, { replace: true })} />
      </div>
      <div style={{ display: "grid", gap: 24, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))", alignItems: "start" }}>
        <section className="panel" style={{ padding: 10 }}>
          <Portrait id={p.player_id} name={p.name} archetype={off?.mix[0]?.id} />
        </section>
        <section className="panel" style={{ gridColumn: "span 2", display: "flex", flexDirection: "column", gap: 14 }}>
          <span className="caption">{t("{season} 赛季 · {family}", { season, family: off ? name(off.family) : t("未分类") })}</span>
          <div className="row" style={{ marginTop: 10, gap: 16, flexWrap: "nowrap", alignItems: "center" }}>
            <h1 className="hero-name">{p.name}</h1>
            <OvrBadge ovr={p.rating?.ovr} size={64} />
            <OffDef off={p.rating?.off} def={p.rating?.def} size={18} />
          </div>
          <div className="row">
            <span className="tag"><TeamLink team={p.team} season={season} long /></span>
            <span className="tag">{t("{n} 场", { n: p.gp })}</span>
            <span className="tag">{t("{n} 分钟", { n: p.minutes.toLocaleString() })}</span>
            {off && <span className="tag" style={{ background: seriesColor(off.mix[0].id), color: "#fff", borderColor: "var(--ink)" }}>{name(off.style)}</span>}
          </div>
          {p.injury && season === playerSeasons.data?.[0] && <InjuryBanner injury={p.injury} />}
          {off?.blend_weight != null ? (
            <p className="bubble" style={{ "--bubble-edge": "var(--pop-yellow)", margin: 0 } as React.CSSProperties}>
              {t("赛季初过渡值：定位、超能力和评分按本赛季 {w} + {prior} 赛季 {pw} 合成，本赛季打得越多，占比越高。", {
                w: `${Math.round(off.blend_weight * 100)}%`, prior: off.prior_season ?? "", pw: `${Math.round((1 - off.blend_weight) * 100)}%` })}
            </p>
          ) : !p.in_fit && (
            <p className="bubble" style={{ "--bubble-edge": "var(--pop-red)", margin: 0 } as React.CSSProperties}>
              {t("样本不足：上场不满 500 分钟，定位和超能力只是投影出来的参考，可信度低。")}
            </p>
          )}
          <div>
            <h2 style={{ fontSize: "var(--size-h2)", marginBottom: 10 }}>{t("超能力")}</h2>
            {powers.length === 0 && <p className="note">{t("没有哪项打法高出联盟平均 1 个标准差以上：一个均衡型选手。")}</p>}
            {powers.map((pw) => (
              <PowerBubble key={pw.feature} power={pw} label={`${t(SIDE_LABEL[pw.side])} · ${label(pw.feature, lang)}`} />
            ))}
          </div>
        </section>
      </div>

      <RatingPanel rating={p.rating} career={p.career_rating} lines={career.data?.regular ?? []} season={season} />

      <section className="panel">
        <span className="caption">{t("战力数值")}</span>
        <div className="row" style={{ justifyContent: "space-around", gap: 18, marginTop: 14 }}>
          {BURSTS.map((b) => {
            const v = p.stats[b.key];
            const rank = p.percentiles[b.key];
            return (
              <div key={b.key} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <Burst value={v == null ? "—" : b.fmt(v)} label={t(b.title)} tone={b.tone} />
                <span className="note">{rank == null ? "" : t("超过 {p} 的球员", { p: pct(rank) })}</span>
              </div>
            );
          })}
        </div>
        <p className="note" style={{ marginTop: 10 }}>{t("比较对象：{season} 赛季满 500 分钟的球员。计数类按每 36 分钟换算。", { season: p.compare_season })}</p>
      </section>

      <div className="grid">
        {(["offense", "defense"] as Side[]).map((side) => {
          const r = p.roles[side];
          if (!r) return null;
          return (
            <section key={side} className="panel">
              <span className="caption">{t("{side}风格", { side: t(SIDE_LABEL[side]) })}</span>
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "var(--font-display)", fontSize: 22 }}>{name(r.style)}</span>
                  <span className="tag">{t("大类：{name}", { name: name(r.family) })}</span>
                </div>
                <MixBar mix={r.mix} height={18} />
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 4 }}>
                  {r.mix.filter((m) => m.weight >= 0.05).map((m) => (
                    <li key={m.id} className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>
                      <span className="swatch" style={{ background: seriesColor(m.id) }} />{name(m.name)} <b>{pct(m.weight)}</b>
                    </li>
                  ))}
                </ul>
                <div>
                  <div className="note" style={{ marginBottom: 6 }}>{t("风格最像的球员（同大类）")}</div>
                  <div className="row">
                    {r.similar.map((s) => (
                      <Link key={s.player_id} to={`/players/${s.player_id}`} className="chip">
                        {s.name}<span style={{ color: "var(--muted)" }}>{pct(s.similarity)}</span>
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            </section>
          );
        })}
      </div>

      <section className="panel">
        <span className="caption">{t("更多数据")}</span>
        <div className="table-box" style={{ marginTop: 12, maxHeight: "none" }}>
          <table className="data">
            <thead><tr><th>{t("指标")}</th><th className="num-col">{t("数值")}</th></tr></thead>
            <tbody>
              {MORE.map((k) => {
                const v = p.stats[k];
                const isPct = /share|pct|rate|^shot_/.test(k);
                return (
                  <tr key={k}><td>{label(k, lang)}</td><td className="num-col">{v == null ? "—" : isPct ? pct(v, 1) : num(v, k.endsWith("cm") || k.endsWith("kg") ? 0 : 1)}</td></tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <RecentGames id={p.player_id} />

      <CareerTable id={p.player_id} season={season} />
    </>
  );
}

function InjuryBanner({ injury }: { injury: Injury }) {
  const { t, lang } = useLang();
  const out = injury.status === "Out";
  const where = injuryWhere(injury, lang);
  return (
    <div className="bubble" style={{ "--bubble-edge": out ? "var(--pop-red)" : "var(--pop-yellow)", margin: 0 } as React.CSSProperties}>
      <div className="row" style={{ gap: 8 }}>
        <span className="tag" style={{ background: out ? "var(--pop-red)" : "var(--pop-yellow)", color: out ? "#fff" : "var(--on-yellow)", fontWeight: 700 }}>
          {out ? t("伤停") : t("出战成疑")}
        </span>
        {where && <b>{where}{injury.detail && lang === "en" ? ` · ${injury.detail}` : ""}</b>}
        {injury.return_date && <span className="note">{t("预计 {date} 前后复出", { date: injury.return_date })}</span>}
      </div>
      {injury.short_comment && <p className="note" style={{ margin: "8px 0 0" }}>{injury.short_comment}</p>}
      <p className="note" style={{ margin: "6px 0 0" }}>
        {t("来源 ESPN，{date} 更新。", { date: new Date(injury.updated_at).toLocaleDateString(lang === "zh" ? "zh-CN" : "en-US") })}
      </p>
    </div>
  );
}

function RecentGames({ id }: { id: number }) {
  const { t } = useLang();
  const q = useRecentGames(id);
  const games = q.data ?? [];
  if (q.isLoading || games.length === 0) return null;
  const n = (v: number | null) => (v == null ? "—" : String(v));
  return (
    <section className="panel">
      <span className="caption">{t("近期比赛")}</span>
      <div className="table-box" style={{ marginTop: 12, maxHeight: "none" }}>
        <table className="data">
          <thead>
            <tr>
              <th>{t("日期")}</th><th>{t("对手")}</th><th>{t("比分")}</th><th className="num-col">{t("分钟")}</th>
              <th className="num-col">{t("得分")}</th><th className="num-col">{t("篮板")}</th><th className="num-col">{t("助攻")}</th>
              <th className="num-col hide-narrow">{t("投篮")}</th><th className="num-col hide-narrow">{t("三分")}</th>
              <th className="num-col hide-narrow">+/-</th>
            </tr>
          </thead>
          <tbody>
            {games.map((g) => {
              const won = g.team_score != null && g.opp_score != null && g.team_score > g.opp_score;
              return (
                <tr key={g.game_id}>
                  <td>{g.game_date.slice(5)}</td>
                  <td>{g.home ? "vs" : "@"} <TeamLink team={g.opp} /></td>
                  <td>{g.team_score == null ? "—" : `${won ? t("胜") : t("负")} ${g.team_score}-${g.opp_score}`}</td>
                  {g.dnp_reason ? (
                    <td colSpan={7} className="note">{t("未出场")} · {g.dnp_reason}</td>
                  ) : (
                    <>
                      <td className="num-col">{n(g.min)}</td><td className="num-col"><b>{n(g.pts)}</b></td>
                      <td className="num-col">{n(g.reb)}</td><td className="num-col">{n(g.ast)}</td>
                      <td className="num-col hide-narrow">{g.fgm}-{g.fga}</td><td className="num-col hide-narrow">{g.fg3m}-{g.fg3a}</td>
                      <td className="num-col hide-narrow">{g.plus_minus == null ? "—" : g.plus_minus > 0 ? `+${g.plus_minus}` : g.plus_minus}</td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ marginTop: 10 }}>{t("每天自动更新，来源 ESPN；只含最近同步到的比赛。")}</p>
    </section>
  );
}

const pg = (total: number | null | undefined, gp: number) => (total == null || !gp ? "—" : (total / gp).toFixed(1));
const rate = (made: number, att: number) => (att ? `${((made / att) * 100).toFixed(1)}%` : "—");
const CAREER_COLS: [string, (l: CareerLine) => string, boolean][] = [
  ["场次", (l) => String(l.gp), true], ["首发", (l) => (l.gs == null ? "—" : String(l.gs)), true],
  ["分钟", (l) => pg(l.min, l.gp), true], ["得分", (l) => pg(l.pts, l.gp), true], ["篮板", (l) => pg(l.reb, l.gp), true],
  ["助攻", (l) => pg(l.ast, l.gp), true], ["抢断", (l) => pg(l.stl, l.gp), false], ["盖帽", (l) => pg(l.blk, l.gp), false],
  ["失误", (l) => pg(l.tov, l.gp), false], ["投篮%", (l) => rate(l.fgm, l.fga), true], ["三分%", (l) => rate(l.fg3m, l.fg3a), true],
  ["罚球%", (l) => rate(l.ftm, l.fta), false],
];

function CareerTable({ id, season }: { id: number; season?: string }) {
  const { t, lang } = useLang();
  const career = useCareer(id);
  const [type, setType] = useState<"regular" | "playoffs">("regular");
  const lines = career.data?.[type] ?? [];
  const total = career.data?.career[type];
  const who = career.data?.player;
  return (
    <section className="panel">
      <span className="caption">{t("生涯数据")}</span>
      <div className="panel-head">
        <p className="note">
          {who?.first_season && t("{first} 至 {last}", { first: who.first_season, last: who.last_season ?? "" })}{who?.first_season ? " · " : ""}
          {t("场均数据；交易赛季显示合并数据。")}
        </p>
        <div className="seg" role="group" aria-label={t("生涯数据")}>
          <button type="button" aria-pressed={type === "regular"} onClick={() => setType("regular")}>{t("常规赛")}</button>
          <button type="button" aria-pressed={type === "playoffs"} onClick={() => setType("playoffs")}>{t("季后赛")}</button>
        </div>
      </div>
      {career.isLoading && <p className="note">…</p>}
      {career.data && lines.length === 0 && (
        <p className="note">{type === "playoffs" && career.data.regular.length ? t("没有季后赛记录。") : t("生涯数据还没采集到。")}</p>
      )}
      {lines.length > 0 && (
        <div className="table-box">
          <table className="data">
            <thead>
              <tr>
                <th>{t("赛季")}</th><th>{t("球队")}</th>{type === "regular" && <><th className="num-col">OVR</th><th className="num-col">{t("攻")}</th><th className="num-col">{t("守")}</th></>}<th className="num-col">{t("年龄")}</th>
                {CAREER_COLS.map(([h, , always]) => <th key={h} className={`num-col${always ? "" : " hide-narrow"}`}>{t(h)}</th>)}
              </tr>
            </thead>
            <tbody>
              {[...lines].reverse().map((l) => (
                <tr key={`${l.season}-${l.team}`} style={l.season === season ? { background: "var(--pop-yellow)", color: "var(--on-yellow)" } : undefined}>
                  <td>{l.season}</td><td>{teamName(l.team, lang)}</td>
                  {type === "regular" && <>
                    <td className="num-col" style={{ fontFamily: "var(--font-latin)", fontSize: 17 }}>{l.ovr ?? "—"}</td>
                    <td className="num-col">{l.off ?? "—"}</td><td className="num-col">{l.def ?? "—"}</td>
                  </>}
                  <td className="num-col">{l.age ?? "—"}</td>
                  {CAREER_COLS.map(([h, f, always]) => <td key={h} className={`num-col${always ? "" : " hide-narrow"}`}>{f(l)}</td>)}
                </tr>
              ))}
              {total && (
                <tr style={{ fontWeight: 700, borderTop: "3px solid var(--ink)" }}>
                  <td>{t("生涯")}</td><td></td>
                  {type === "regular" && <>
                    <td className="num-col" style={{ fontFamily: "var(--font-latin)", fontSize: 17 }}>{career.data?.rating?.career.toFixed(1) ?? "—"}</td>
                    <td className="num-col">{career.data?.rating?.off_career?.toFixed(1) ?? "—"}</td>
                    <td className="num-col">{career.data?.rating?.def_career?.toFixed(1) ?? "—"}</td>
                  </>}
                  <td></td>
                  {CAREER_COLS.map(([h, f, always]) => <td key={h} className={`num-col${always ? "" : " hide-narrow"}`}>{f(total)}</td>)}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
