import { useEffect, useRef, useState } from "react";
import { CareerLine, CareerRating, SeasonRating } from "../api";
import { useLang } from "../i18n";
import { Burst } from "./comic";

/** Small OVR badge for cards. */
export function OvrBadge({ ovr, size = 40 }: { ovr: number | null | undefined; size?: number }) {
  if (ovr == null) return null;
  const tone = ovr >= 90 ? "var(--pop-red)" : ovr >= 80 ? "var(--pop-yellow)" : "var(--panel)";
  const ink = ovr >= 90 ? "#fff" : ovr >= 80 ? "#111" : "var(--ink)";
  return (
    <span aria-label={`OVR ${ovr}`} style={{
      display: "inline-grid", placeItems: "center", width: size, height: size, flex: "none",
      background: tone, color: ink, border: "2px solid var(--ink)", boxShadow: "2px 2px 0 var(--ink)",
      fontFamily: "var(--font-latin)", fontSize: size * 0.55, lineHeight: 1,
    }}>{ovr}</span>
  );
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

function Trend({ lines, season, career }: { lines: CareerLine[]; season?: string; career: CareerRating | null }) {
  const { t } = useLang();
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);
  const pts = lines.filter((l) => l.ovr != null && l.season);
  const h = 236, m = { l: 34, r: 12, t: 30, b: 30 };
  const lo = 40, hi = 100;
  const x = (i: number) => m.l + (pts.length < 2 ? (w - m.l - m.r) / 2 : (i / (pts.length - 1)) * (w - m.l - m.r));
  const y = (v: number) => m.t + ((hi - v) / (hi - lo)) * (h - m.t - m.b);
  const peakIdx = career ? [pts.findIndex((p) => p.season === career.peak_from), pts.findIndex((p) => p.season === career.peak_to)] : [-1, -1];
  const step = Math.max(1, Math.ceil(pts.length / Math.max(2, Math.floor(w / 70))));
  const sel = pts.findIndex((p) => p.season === season);
  // Axis labels: the selected season always, others on a stride, never right next to the selected one.
  const showLabel = (i: number) => i === sel || ((i % step === 0 || i === pts.length - 1) && (sel < 0 || Math.abs(i - sel) >= Math.max(2, step)));
  return (
    <div ref={box} style={{ minHeight: h }}>
      {w > 0 && pts.length > 0 && (
        <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label={t("各赛季评分")}>
          {[50, 60, 70, 80, 90, 100].map((v) => (
            <g key={v}>
              <line x1={m.l} x2={w - m.r} y1={y(v)} y2={y(v)} stroke="var(--rule)" />
              <text x={m.l - 6} y={y(v)} textAnchor="end" dominantBaseline="middle" fontSize="11" fill="var(--muted)">{v}</text>
            </g>
          ))}
          {peakIdx[0] >= 0 && peakIdx[1] >= 0 && (
            <rect x={x(peakIdx[0]) - 8} width={x(peakIdx[1]) - x(peakIdx[0]) + 16} y={m.t} height={h - m.t - m.b}
              fill="var(--pop-yellow)" opacity="0.35" />
          )}
          <polyline fill="none" stroke="var(--ink)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"
            points={pts.map((p, i) => `${x(i)},${y(p.ovr!)}`).join(" ")} />
          {pts.map((p, i) => (
            <g key={p.season}>
              <circle cx={x(i)} cy={y(p.ovr!)} r={p.season === season ? 7 : 4.5}
                fill={p.season === season ? "var(--pop-red)" : p.ovr_qualified ? "var(--panel)" : "var(--rule)"}
                stroke="var(--ink)" strokeWidth="2">
                <title>{`${p.season} · OVR ${p.ovr}`}</title>
              </circle>
              {showLabel(i) && (
                <text x={x(i)} y={h - 10} textAnchor="middle" fontSize="11" fill={p.season === season ? "var(--ink)" : "var(--muted)"}
                  fontWeight={p.season === season ? 700 : 400}>{p.season!.slice(2)}</text>
              )}
              {p.season === season && (
                <text x={Math.min(w - m.r - 10, Math.max(m.l + 10, x(i)))} y={y(p.ovr!) - 22 < 4 ? y(p.ovr!) + 26 : y(p.ovr!) - 12}
                  textAnchor="middle" fontFamily="var(--font-latin)" fontSize="18" fill="var(--ink)"
                  paintOrder="stroke" stroke="var(--panel)" strokeWidth="4" strokeLinejoin="round">{p.ovr}</text>
              )}
            </g>
          ))}
        </svg>
      )}
    </div>
  );
}

export function RatingPanel({ rating, career, lines, season }: {
  rating: SeasonRating | null; career: CareerRating | null; lines: CareerLine[]; season?: string;
}) {
  const { t } = useLang();
  const d = rating?.detail;
  return (
    <section className="panel">
      <span className="caption">{t("能力值")}</span>
      <div style={{ display: "grid", gap: 24, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", marginTop: 14 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="row" style={{ gap: 18, flexWrap: "nowrap" }}>
            {rating ? <Burst value={String(rating.ovr)} label={t("{season} 综合评分", { season: season ?? "" })} /> : <p className="note">{t("这个赛季还没有评分。")}</p>}
            {career && (
              <div style={{ display: "grid", gap: 6 }}>
                <div><span className="note">{t("巅峰评分")}</span><div style={{ fontFamily: "var(--font-latin)", fontSize: 30, lineHeight: 1 }}>{career.peak.toFixed(1)}</div>
                  <span className="note">{career.peak_from === career.peak_to ? career.peak_from : `${career.peak_from} – ${career.peak_to}`}</span></div>
                <div><span className="note">{t("生涯评分")}</span><div style={{ fontFamily: "var(--font-latin)", fontSize: 30, lineHeight: 1 }}>{career.career.toFixed(1)}</div>
                  <span className="note">{t("{n} 个赛季，其中 {q} 季满 500 分钟", { n: career.seasons, q: career.qualified_seasons })}</span></div>
              </div>
            )}
          </div>
          {rating && d && (
            <>
              <ComponentRow title={t("综合贡献")} weight={0.4} z={d.contribution} detail={t("PIE {v}：他占场上所有统计事件的份额", { v: pct1(d.pie) })} />
              <ComponentRow title={t("得分效率与量")} weight={0.4} z={d.scoring}
                detail={t("使用率 {usg}，真实命中率 {ts}（联盟 {lg}）", { usg: pct1(d.usg), ts: pct1(d.ts), lg: pct1(d.league_ts) })} />
              <ComponentRow title={t("在场表现")} weight={0.2} z={d.on_court} detail={t("他在场时球队每 100 回合净胜 {net} 分", { net: signed(d.net) })} />
              <p className="note" style={{ margin: 0 }}>
                {t("样本权重 {w}（{min} 分钟）：样本越少，评分越向替补水平靠拢。", { w: `${Math.round(d.reliability * 100)}%`, min: Math.round(rating.minutes).toLocaleString() })}
                {rating.baseline_season !== season && ` ${t("本赛季还早，按 {s} 赛季的标准换算。", { s: rating.baseline_season })}`}
              </p>
            </>
          )}
        </div>
        <div>
          <div className="note" style={{ marginBottom: 6 }}>{t("各赛季评分（黄色区域是巅峰三季）")}</div>
          <Trend lines={lines} season={season} career={career} />
        </div>
      </div>
      <details style={{ marginTop: 16 }}>
        <summary style={{ cursor: "pointer", fontFamily: "var(--font-display)", fontSize: 18 }}>{t("评分是怎么算的？")}</summary>
        <ol style={{ margin: "10px 0 0", paddingLeft: "1.3em", display: "grid", gap: 6, maxWidth: "75ch" }}>
          <li>{t("每个赛季用联盟官方的全员数据，算三项指标：综合贡献（PIE，占场上统计事件的份额）、得分效率与量（使用率 × 真实命中率高出联盟的部分，再加上球权本身的价值）、在场表现（他在场时球队的净效率，按上场时间打折，因为它受队友影响很大）。")}</li>
          <li>{t("每项都和同赛季满 500 分钟的球员比，换成标准差（σ），按 40% / 40% / 20% 加权合成。")}</li>
          <li>{t("按上场时间做收缩：分钟越少，越向替补水平靠拢，避免几场比赛就打出 95 分。")}</li>
          <li>{t("换算成 2K 式分数：77 + 6.5 × σ，范围 40–99。联盟中位数约 75，前 10% 约 82 以上，最顶尖接近 99。")}</li>
          <li>{t("巅峰评分 = 生涯中连续三个满 500 分钟赛季的最高平均；生涯评分 = 70% 巅峰 + 30% 各赛季按分钟加权的平均。")}</li>
        </ol>
        <p className="note" style={{ marginTop: 10 }}>{t("这是第一版（只用 box score）。它偏爱篮板多、出手效率高的内线；之后会换成考虑队友和对手的影响力模型（RAPM）。每个赛季都在当季内排名，所以不同年代可以直接比较。")}</p>
      </details>
    </section>
  );
}
