import { useEffect, useRef, useState } from "react";
import { CareerLine, CareerRating, SeasonRating } from "../api";
import { useLang } from "../i18n";
import { Burst } from "./comic";

export type RatingKey = "ovr" | "off" | "def";
export const RATING_LABEL: Record<RatingKey, string> = { ovr: "综合", off: "进攻", def: "防守" };
const RATING_SHORT: Record<RatingKey, { zh: string; en: string }> = {
  ovr: { zh: "综合", en: "OVR" }, off: { zh: "攻", en: "OFF" }, def: { zh: "守", en: "DEF" },
};

/** Small OVR badge for cards: a dark card plate in the rating's 2K tier (edge colour, glow, shine). */
export function OvrBadge({ ovr, size = 40 }: { ovr: number | null | undefined; size?: number }) {
  if (ovr == null) return null;
  return (
    <span aria-label={`OVR ${ovr}`} className={`plate plate-${tierOf(ovr)}`} style={{
      width: size, height: size, fontFamily: "var(--font-latin)", fontSize: size * 0.55, lineHeight: 1,
    }}><TierNumber value={ovr} /></span>
  );
}

/** Offense and defense next to each other: "攻 87 守 81". */
export function OffDef({ off, def, size = 15 }: { off: number | null | undefined; def: number | null | undefined; size?: number }) {
  const { lang } = useLang();
  if (off == null && def == null) return null;
  const cell = (k: "off" | "def", v: number | null | undefined) => v == null ? null : (
    <span aria-label={`${RATING_SHORT[k].en} ${v}`} style={{ display: "inline-flex", alignItems: "baseline", gap: 3 }}>
      <span style={{ fontSize: size * 0.72, color: "var(--muted)", fontWeight: 700 }}>{RATING_SHORT[k][lang]}</span>
      <span className={`plate plate-sm plate-${tierOf(v)}`} style={{ fontFamily: "var(--font-latin)", fontSize: size * 1.15, lineHeight: 1, padding: "2px 5px" }}>
        <TierNumber value={v} />
      </span>
    </span>
  );
  return <span style={{ display: "inline-flex", gap: 8, alignItems: "baseline" }}>{cell("off", off)}{cell("def", def)}</span>;
}

const TIERS: [number, string, string, string][] = [
  [96, "opal", "银河蛋白石", "Galaxy opal"], [92, "diamond", "钻石", "Diamond"], [87, "amethyst", "紫晶", "Amethyst"],
  [80, "gold", "金", "Gold"], [70, "silver", "银", "Silver"], [0, "bronze", "铜", "Bronze"],
];

function tierOf(value: number) {
  return TIERS.find(([min]) => value >= min)![1];
}

/** A rating number dressed in its 2K-style card tier: the higher, the fancier. */
export function TierNumber({ value, digits = 0 }: { value: number; digits?: number }) {
  const { lang } = useLang();
  const [, cls, zh, en] = TIERS.find(([min]) => value >= min)!;
  return <span className={`tier-num tier-${cls}`} title={lang === "zh" ? zh : en}>{value.toFixed(digits)}</span>;
}

const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;
const signed = (v: number, d = 1) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(d)}`;

function ComponentRow({ title, weight, z, detail }: { title: string; weight: number; z: number; detail: string }) {
  const clamped = Math.max(-3, Math.min(3, z));
  const left = clamped < 0 ? 50 + (clamped / 3) * 50 : 50;
  const width = Math.abs(clamped / 3) * 50;
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
        <span style={{ fontWeight: 700 }}>{title} <span className="note">×{weight}</span></span>
        <span style={{ fontFamily: "var(--font-latin)", fontSize: 18 }}>{signed(z)}σ</span>
      </div>
      <div style={{ position: "relative", height: 12, border: "2px solid var(--ink)", background: "var(--panel)" }} aria-hidden="true">
        <span style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 2, background: "var(--ink)" }} />
        <span style={{ position: "absolute", top: 0, bottom: 0, left: `${left}%`, width: `${width}%`, background: z >= 0 ? "var(--pop-red)" : "var(--pop-blue)" }} />
      </div>
      <span className="note">{detail}</span>
    </div>
  );
}

function Trend({ lines, season, metric }: { lines: CareerLine[]; season?: string; metric: RatingKey }) {
  const { t } = useLang();
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);
  const pts = lines.filter((l) => l[metric] != null && l.season).map((l) => ({ ...l, v: l[metric] as number }));
  const h = 236, m = { l: 34, r: 12, t: 30, b: 30 };
  const lo = 40, hi = 100;
  const x = (i: number) => m.l + (pts.length < 2 ? (w - m.l - m.r) / 2 : (i / (pts.length - 1)) * (w - m.l - m.r));
  const y = (v: number) => m.t + ((hi - v) / (hi - lo)) * (h - m.t - m.b);
  const step = Math.max(1, Math.ceil(pts.length / Math.max(2, Math.floor(w / 70))));
  const sel = pts.findIndex((p) => p.season === season);
  // Axis labels: the selected season always, others on a stride, never right next to the selected one.
  const showLabel = (i: number) => i === sel || ((i % step === 0 || i === pts.length - 1) && (sel < 0 || Math.abs(i - sel) >= Math.max(2, step)));
  return (
    <div ref={box} style={{ minHeight: h, position: "relative" }}>
      {w > 0 && pts.length > 0 && (
        <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label={t("各赛季评分")}
          onPointerMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - r.left) / r.width) * w;
            let best = 0;
            pts.forEach((_p, i) => { if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i; });
            setHover(best);
          }}
          onPointerLeave={() => setHover(null)}>
          {[50, 60, 70, 80, 90, 100].map((v) => (
            <g key={v}>
              <line x1={m.l} x2={w - m.r} y1={y(v)} y2={y(v)} stroke="var(--rule)" />
              <text x={m.l - 6} y={y(v)} textAnchor="end" dominantBaseline="middle" fontSize="11" fill="var(--muted)">{v}</text>
            </g>
          ))}
          {hover != null && (
            <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={h - m.b} stroke="var(--ink)" strokeDasharray="3 3" opacity="0.5" />
          )}
          <polyline fill="none" stroke="var(--ink)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"
            points={pts.map((p, i) => `${x(i)},${y(p.v)}`).join(" ")} />
          {pts.map((p, i) => (
            <g key={p.season}>
              <circle cx={x(i)} cy={y(p.v)} r={p.season === season ? 7 : hover === i ? 6.5 : 4.5}
                fill={p.season === season ? "var(--pop-red)" : hover === i ? "var(--pop-yellow)" : p.ovr_qualified ? "var(--panel)" : "var(--rule)"}
                stroke="var(--ink)" strokeWidth="2" />
              {showLabel(i) && (
                <text x={x(i)} y={h - 10} textAnchor="middle" fontSize="11" fill={p.season === season ? "var(--ink)" : "var(--muted)"}
                  fontWeight={p.season === season ? 700 : 400}>{p.season!.slice(2)}</text>
              )}
              {p.season === season && (
                <text x={Math.min(w - m.r - 10, Math.max(m.l + 10, x(i)))} y={y(p.v) - 22 < 4 ? y(p.v) + 26 : y(p.v) - 12}
                  textAnchor="middle" fontFamily="var(--font-latin)" fontSize="18" fill="var(--ink)"
                  paintOrder="stroke" stroke="var(--panel)" strokeWidth="4" strokeLinejoin="round">{p.v}</text>
              )}
            </g>
          ))}
        </svg>
      )}
      {hover != null && pts[hover] && (
        <div role="status" style={{
          position: "absolute", pointerEvents: "none", top: Math.max(0, (y(pts[hover].v) / h) * (box.current?.clientHeight ?? h) - 54),
          left: `${(x(hover) / w) * 100}%`, transform: `translateX(${x(hover) > w * 0.75 ? "-100%" : x(hover) < w * 0.25 ? "0" : "-50%"})`,
          background: "var(--panel)", border: "2px solid var(--ink)", boxShadow: "2px 2px 0 var(--ink)", padding: "4px 8px",
          whiteSpace: "nowrap", fontSize: "var(--size-caption)",
        }}>
          <b>{pts[hover].season}</b>{pts[hover].team ? ` · ${pts[hover].team}` : ""}
          <span style={{ fontFamily: "var(--font-latin)", fontSize: 18, marginLeft: 8 }}>{pts[hover].v}</span>
          <span className="note"> {t(RATING_LABEL[metric])}</span>
        </div>
      )}
    </div>
  );
}

function Breakdown({ metric, rating }: { metric: RatingKey; rating: SeasonRating }) {
  const { t } = useLang();
  const d = rating.detail;
  if (metric === "off") {
    const o = d.off;
    return (
      <>
        <ComponentRow title={t("得分效率与量")} weight={0.45} z={o.scoring}
          detail={t("使用率 {usg}，真实命中率 {ts}（联盟 {lg}）", { usg: pct1(d.usg), ts: pct1(d.ts), lg: pct1(d.league_ts) })} />
        <ComponentRow title={t("组织")} weight={0.25} z={o.playmaking}
          detail={t("助攻率 {ast}，失误率 {tov}", { ast: pct1(o.ast_pct), tov: `${o.tov_pct.toFixed(1)}%` })} />
        <ComponentRow title={t("进攻篮板")} weight={0.1} z={o.off_rebounding} detail={t("进攻篮板率 {v}", { v: pct1(o.oreb_pct) })} />
        <ComponentRow title={t("在场进攻")} weight={0.2} z={o.on_court}
          detail={t("他在场时球队每 100 回合得 {on} 分（联盟 {lg}）", { on: o.ortg.toFixed(1), lg: o.league_ortg.toFixed(1) })} />
      </>
    );
  }
  if (metric === "def") {
    const e = d.def;
    return (
      <>
        <ComponentRow title={t("抢断")} weight={0.2} z={e.steals} detail={t("每 36 分钟 {v} 次", { v: e.stl_36.toFixed(1) })} />
        <ComponentRow title={t("盖帽")} weight={0.15} z={e.blocks} detail={t("每 36 分钟 {v} 次", { v: e.blk_36.toFixed(1) })} />
        <ComponentRow title={t("防守篮板")} weight={0.15} z={e.def_rebounding} detail={t("防守篮板率 {v}", { v: pct1(e.dreb_pct) })} />
        <ComponentRow title={t("在场防守")} weight={0.5} z={e.on_court}
          detail={t("他在场时球队每 100 回合失 {on} 分（联盟 {lg}）", { on: e.drtg.toFixed(1), lg: e.league_drtg.toFixed(1) })} />
      </>
    );
  }
  return (
    <>
      <ComponentRow title={t("综合贡献")} weight={0.4} z={d.contribution} detail={t("PIE {v}：他占场上所有统计事件的份额", { v: pct1(d.pie) })} />
      <ComponentRow title={t("得分效率与量")} weight={0.4} z={d.scoring}
        detail={t("使用率 {usg}，真实命中率 {ts}（联盟 {lg}）", { usg: pct1(d.usg), ts: pct1(d.ts), lg: pct1(d.league_ts) })} />
      <ComponentRow title={t("在场表现")} weight={0.2} z={d.on_court} detail={t("他在场时球队每 100 回合净胜 {net} 分", { net: signed(d.net) })} />
    </>
  );
}

function Score({ label, value, digits = 0, sub }: { label: string; value: number; digits?: number; sub?: string }) {
  return (
    <div>
      <span className="note">{label}</span>
      <div style={{ fontFamily: "var(--font-latin)", fontSize: 30, lineHeight: 1 }}><TierNumber value={value} digits={digits} /></div>
      {sub && <span className="note">{sub}</span>}
    </div>
  );
}

export function RatingPanel({ rating, career, lines, season }: {
  rating: SeasonRating | null; career: CareerRating | null; lines: CareerLine[]; season?: string;
}) {
  const { t } = useLang();
  const [metric, setMetric] = useState<RatingKey>("ovr");
  const d = rating?.detail;
  const careerOf = { ovr: career?.career, off: career?.off_career, def: career?.def_career };
  const peakOf = { ovr: career?.peak, off: career?.off_peak, def: career?.def_peak };
  return (
    <section className="panel">
      <span className="caption">{t("能力值")}</span>
      <div style={{ display: "grid", gap: 24, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", marginTop: 14 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="row" style={{ gap: 18, flexWrap: "wrap", alignItems: "center" }}>
            {rating ? <Burst value={<TierNumber value={rating.ovr} />} label={t("{season} 综合评分", { season: season ?? "" })} /> : <p className="note">{t("这个赛季还没有评分。")}</p>}
            {rating && (
              <div style={{ display: "grid", gap: 8 }}>
                <Score label={t("进攻评分")} value={rating.off} />
                <Score label={t("防守评分")} value={rating.def} />
              </div>
            )}
            {career && (
              <div style={{ display: "grid", gap: 6 }}>
                <Score label={t("巅峰评分")} value={career.peak} digits={1}
                  sub={career.peak_from === career.peak_to ? career.peak_from : `${career.peak_from} – ${career.peak_to}`} />
                <Score label={t("生涯评分")} value={career.career} digits={1}
                  sub={t("{n} 个赛季，其中 {q} 季满 500 分钟", { n: career.seasons, q: career.qualified_seasons })} />
              </div>
            )}
          </div>
          <div className="seg" role="group" aria-label={t("评分类型")} style={{ alignSelf: "flex-start" }}>
            {(["ovr", "off", "def"] as RatingKey[]).map((k) => (
              <button key={k} type="button" aria-pressed={metric === k} onClick={() => setMetric(k)}>{t(RATING_LABEL[k])}</button>
            ))}
          </div>
          {rating && d && (
            <>
              <Breakdown metric={metric} rating={rating} />
              {d.blend && (
                <p className="note" style={{ margin: 0 }}>
                  {t("过渡值 = {w} × 本赛季 {own} + {pw} × {prior} 赛季 {p}", {
                    w: `${Math.round(d.blend.weight * 100)}%`, pw: `${Math.round((1 - d.blend.weight) * 100)}%`,
                    own: d.blend[`own_${metric}`], prior: d.blend_prior ?? "", p: d.blend[`prior_${metric}`] })}
                </p>
              )}
              {!d.blend && <p className="note" style={{ margin: 0 }}>
                {t("样本权重 {w}（{min} 分钟）：样本越少，评分越向替补水平靠拢。", { w: `${Math.round(d.reliability * 100)}%`, min: Math.round(rating.minutes).toLocaleString() })}
                {rating.baseline_season !== season && ` ${t("本赛季还早，按 {s} 赛季的标准换算。", { s: rating.baseline_season })}`}
              </p>}
            </>
          )}
        </div>
        <div>
          <div className="note" style={{ marginBottom: 6 }}>
            {metric === "ovr" ? t("各赛季评分") : t("各赛季{k}评分", { k: t(RATING_LABEL[metric]) })}
          </div>
          <Trend lines={lines} season={season} metric={metric} />
          {career && metric !== "ovr" && peakOf[metric] != null && (
            <p className="note" style={{ margin: "6px 0 0" }}>
              {t("{k}巅峰 {p}，生涯 {c}", { k: t(RATING_LABEL[metric]), p: peakOf[metric]!.toFixed(1), c: careerOf[metric]!.toFixed(1) })}
            </p>
          )}
        </div>
      </div>
      <details style={{ marginTop: 16 }}>
        <summary style={{ cursor: "pointer", fontFamily: "var(--font-display)", fontSize: 18 }}>{t("评分是怎么算的？")}</summary>
        <ol style={{ margin: "10px 0 0", paddingLeft: "1.3em", display: "grid", gap: 6, maxWidth: "75ch" }}>
          <li>{t("每个赛季用联盟官方的全员数据，算三项指标：综合贡献（PIE，占场上统计事件的份额）、得分效率与量（使用率 × 真实命中率高出联盟的部分，再加上球权本身的价值）、在场表现（他在场时球队的净效率，按上场时间打折，因为它受队友影响很大）。")}</li>
          <li>{t("每项都和同赛季满 500 分钟的球员比，换成标准差（σ），按 40% / 40% / 20% 加权合成。")}</li>
          <li>{t("进攻评分：得分效率与量 45%、组织（助攻率减一半失误率）25%、进攻篮板 10%、在场进攻 20%。")}</li>
          <li>{t("防守评分：抢断 20%、盖帽 15%、防守篮板 15%、在场防守 50%。在场数据和他自己球队比（再加三成球队整体水平），所以防守好的球队不会把每个人都抬高。")}</li>
          <li>{t("按上场时间做收缩：分钟越少，越向替补水平靠拢，避免几场比赛就打出 95 分。")}</li>
          <li>{t("换算成 2K 式分数：77 + 6.5 × σ，范围 40–99。联盟中位数约 75，前 10% 约 82 以上，最顶尖接近 99。三项评分各自独立计算，综合评分不是攻守的平均。")}</li>
          <li>{t("巅峰评分 = 生涯中连续三个满 500 分钟赛季的最高平均；生涯评分 = 70% 巅峰 + 30% 各赛季按分钟加权的平均。")}</li>
          <li>{t("进行中的赛季：本赛季权重 = 分钟 ÷（分钟 + 600），其余来自上赛季。约 5 场首发（170 分钟）时本赛季占 22%，600 分钟占一半，1800 分钟占 75%。新秀没有上赛季，样本少时向替补水平靠拢。")}</li>
          <li>{t("数字的颜色是 2K 式卡牌等级：铜（70 以下）、银（70+）、金（80+）、紫晶（87+）、钻石（92+）、银河蛋白石（96+）。")}</li>
        </ol>
        <p className="note" style={{ marginTop: 10 }}>{t("这是第一版（只用 box score）。它偏爱篮板多、出手效率高的内线；防守尤其难从 box score 看出来，换防、协防和限制投篮都看不到。之后会换成考虑队友和对手的影响力模型（RAPM）。每个赛季都在当季内排名，所以不同年代可以直接比较。")}</p>
      </details>
    </section>
  );
}
