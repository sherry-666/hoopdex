import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { Axis, RolePlayer, RoleType, Side, seriesColor } from "../api";
import { label, labelList, PROFILE_FEATURES } from "../labels";
import { useLang } from "../i18n";
import { teamName } from "../teams";

/* ---------- shared helpers ---------- */

function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/** Bumps when the colour theme changes, so canvas-like drawings that resolve CSS
 * colours to values redraw. */
function useThemeTick(): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const bump = () => setTick((t) => t + 1);
    const mo = new MutationObserver(bump);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", bump);
    return () => { mo.disconnect(); mq.removeEventListener("change", bump); };
  }, []);
  return tick;
}

const cssColor = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function showTip(box: HTMLElement, lines: [string, string][], x: number, y: number) {
  let tip = box.querySelector<HTMLDivElement>(".tip");
  if (!tip) { tip = document.createElement("div"); tip.className = "tip"; box.appendChild(tip); }
  tip.replaceChildren(...lines.map(([k, v]) => {
    const d = document.createElement("div");
    if (k) { const s = document.createElement("span"); s.style.color = "var(--muted)"; s.textContent = k + " "; d.appendChild(s); }
    const b = document.createElement("b"); b.textContent = v; d.appendChild(b);
    return d;
  }));
  tip.hidden = false;
  tip.style.left = `${Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, x + 14))}px`;
  tip.style.top = `${Math.max(0, y - tip.offsetHeight - 12)}px`;
}
const hideTip = (box: HTMLElement) => { const t = box.querySelector<HTMLDivElement>(".tip"); if (t) t.hidden = true; };

const mixText = (p: RolePlayer, names: Map<number, string>) =>
  Object.entries(p.weights).sort((a, b) => b[1] - a[1]).filter(([, w]) => w >= 0.1)
    .map(([id, w]) => `${names.get(+id)} ${Math.round(w * 100)}%`).join(" · ");

interface Look { color: string; alpha: number; r: number; front: number }
function look(p: RolePlayer, pick: number | null): Look {
  if (pick != null) {
    const w = p.weights[String(pick)] ?? 0;
    return { color: seriesColor(pick), alpha: 0.08 + 0.92 * w, r: 3 + 3.5 * w, front: w };
  }
  return { color: seriesColor(p.top_archetype_id), alpha: 0.25 + 0.75 * p.top_weight, r: 4.5, front: 1 };
}

interface Label { name: string; id: number; x: number; y: number; w?: number; lx?: number; ty?: number }
function placeLabels(labels: Label[], w: number, h: number, lh = 18) {
  const placed: Label[] = [];
  for (const l of [...labels].sort((a, b) => a.y - b.y)) {
    l.lx = Math.max((l.w ?? 0) / 2 + 4, Math.min(w - (l.w ?? 0) / 2 - 4, l.x));
    let ty = Math.max(lh, l.y);
    let moved = true;
    while (moved) {
      moved = false;
      for (const p of placed) {
        if (Math.abs(p.lx! - l.lx) < ((p.w ?? 0) + (l.w ?? 0)) / 2 + 6 && Math.abs(p.ty! - ty) < lh) { ty = p.ty! + lh; moved = true; }
      }
    }
    l.ty = Math.min(h - 6, ty);
    placed.push(l);
  }
}

function drawLabels(svg: d3.Selection<SVGSVGElement, unknown, null, undefined>, labels: Label[], w: number, h: number,
  pick: number | null, onPick: (id: number | null) => void) {
  const t = svg.append("g").selectAll<SVGTextElement, Label>("text").data(labels).join("text")
    .text((l) => l.name).attr("text-anchor", "middle")
    .style("font-family", "var(--font-display)").style("font-size", "15px").style("fill", "var(--ink)")
    .style("paint-order", "stroke").style("stroke", "var(--panel)").style("stroke-width", 5).style("stroke-linejoin", "round")
    .style("opacity", (l) => (pick == null || l.id === pick ? 1 : 0.5)).style("cursor", "pointer")
    .on("click", (_e, l) => onPick(l.id === pick ? null : l.id));
  t.each(function (l) { l.w = this.getComputedTextLength(); });
  placeLabels(labels, w, h);
  t.attr("x", (l) => l.lx!).attr("y", (l) => l.ty!);
}

function attachHover(svg: d3.Selection<SVGSVGElement, unknown, null, undefined>, box: HTMLElement, pts: RolePlayer[],
  xf: (p: RolePlayer) => number, yf: (p: RolePlayer) => number, scale: () => number,
  lines: (p: RolePlayer) => [string, string][], onPick: (id: number | null) => void, dragEnd: { at: number },
  onOpen: (id: number) => void) {
  const delaunay = d3.Delaunay.from(pts, xf, yf);
  const ring = svg.append("circle").attr("r", 8).style("fill", "none").style("stroke", "var(--ink)").style("stroke-width", 2).style("display", "none");
  const nearest = (e: PointerEvent | MouseEvent) => {
    const [mx, my] = d3.pointer(e);
    const p = pts[delaunay.find(mx, my)];
    return p && Math.hypot(xf(p) - mx, yf(p) - my) <= 24 ? p : null;
  };
  svg.on("mousemove", (e: MouseEvent) => {
    const p = nearest(e);
    if (!p) { ring.style("display", "none"); hideTip(box); return; }
    ring.style("display", null).attr("cx", xf(p)).attr("cy", yf(p));
    showTip(box, lines(p), xf(p) * scale(), yf(p) * scale());
  }).on("mouseleave", () => { ring.style("display", "none"); hideTip(box); })
    .on("click", (e: MouseEvent) => {
      if (Date.now() - dragEnd.at < 250) return;
      const p = nearest(e);
      if (p) onOpen(p.player_id);
      else onPick(null);
    });
}

/* ---------- cluster view ---------- */

const VIEW = { yaw: -0.65, pitch: 0.38 };
const clamp = (v: number) => Math.max(-3.2, Math.min(3.2, v));
const shortName = (n: string) => n.split(/（| \(/)[0];
type AxisKey = "f1" | "f2" | "f3" | "l1" | "l2" | "l3";

export function ClusterView({ players, axes, archetypes, pick, onPick, onOpen, includeLow = false }: {
  players: RolePlayer[]; axes: Axis[]; archetypes: RoleType[]; pick: number | null;
  onPick: (id: number | null) => void; onOpen: (id: number) => void; includeLow?: boolean;
}) {
  const [box, width] = useWidth<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const [set, setSet] = useState<"factor" | "lda">("factor");
  const [dim, setDim] = useState<2 | 3>(3);
  const [core, setCore] = useState(true);
  const [pair, setPair] = useState<Record<"factor" | "lda", [AxisKey, AxisKey]>>({ factor: ["f1", "f2"], lda: ["l1", "l2"] });
  const view = useRef({ ...VIEW });
  const [, setRedraw] = useState(0);
  const theme = useThemeTick();
  const { t, name, lang } = useLang();
  const shown = axes.filter((a) => a.method === set);
  const used: AxisKey[] = dim === 3 ? (shown.map((a) => a.axis) as AxisKey[]) : pair[set];
  const byAxis = new Map(axes.map((a) => [a.axis, a]));

  useEffect(() => {
    const el = box.current, svgEl = svgRef.current;
    if (!el || !svgEl || !width) return;
    const names = new Map(archetypes.map((a) => [a.type_id, name(a.name)]));
    const pts = players.filter((p) => (p.in_fit || includeLow) && (!core || p.top_weight >= 0.5));
    const w = width, h = Math.round(Math.max(380, Math.min(620, w * 0.62)));
    const svg = d3.select(svgEl).attr("viewBox", `0 0 ${w} ${h}`).attr("width", "100%");
    const lines = (p: RolePlayer): [string, string][] => [
      ["", `${p.name} · ${teamName(p.team, lang)}`], [t("风格构成"), mixText(p, names)],
      ...used.map((k): [string, string] => [shortName(name(byAxis.get(k)?.name ?? k)), `${p[k] >= 0 ? "+" : ""}${p[k].toFixed(1)}σ`]),
    ];
    const dragEnd = { at: 0 };
    const archLabels = (xy: (...v: number[]) => number[]): Label[] => archetypes.map((a) => {
      const ms = pts.filter((p) => p.top_archetype_id === a.type_id && p.top_weight >= 0.5);
      if (!ms.length) return null;
      const [x, y] = xy(...used.map((k) => d3.median(ms, (p) => clamp(p[k]))!));
      return { name: name(a.name), id: a.type_id, x, y: y - 14 };
    }).filter((l): l is Label => l !== null);

    const render = () => {
      svg.selectAll("*").remove();
      if (dim === 2) {
        const [kx, ky] = used;
        const x = d3.scaleLinear([-3.2, 3.2], [44, w - 16]), y = d3.scaleLinear([-3.2, 3.2], [h - 40, 18]);
        const ticks = [-3, -2, -1, 0, 1, 2, 3];
        const g = svg.append("g");
        g.selectAll("line.v").data(ticks).join("line").attr("x1", (t) => x(t)).attr("x2", (t) => x(t)).attr("y1", 18).attr("y2", h - 40)
          .style("stroke", (t) => (t === 0 ? "var(--ink)" : "var(--rule)")).style("stroke-width", (t) => (t === 0 ? 2 : 1));
        g.selectAll("line.h").data(ticks).join("line").attr("y1", (t) => y(t)).attr("y2", (t) => y(t)).attr("x1", 44).attr("x2", w - 16)
          .style("stroke", (t) => (t === 0 ? "var(--ink)" : "var(--rule)")).style("stroke-width", (t) => (t === 0 ? 2 : 1));
        const tickStyle = (s: d3.Selection<SVGTextElement, number, SVGGElement, unknown>) =>
          s.style("font-size", "12px").style("fill", "var(--muted)");
        g.selectAll<SVGTextElement, number>("text.tx").data(ticks).join("text").call(tickStyle)
          .attr("x", (t) => x(t)).attr("y", h - 22).attr("text-anchor", "middle").text((t) => `${t > 0 ? "+" : t < 0 ? "−" : ""}${Math.abs(t)}σ`);
        g.selectAll<SVGTextElement, number>("text.ty").data(ticks).join("text").call(tickStyle)
          .attr("x", 36).attr("y", (t) => y(t)).attr("text-anchor", "end").attr("dominant-baseline", "middle").text((t) => `${t > 0 ? "+" : t < 0 ? "−" : ""}${Math.abs(t)}`);
        svg.append("text").attr("x", w - 16).attr("y", h - 4).attr("text-anchor", "end").style("font-size", "13px").style("fill", "var(--ink-soft)")
          .text(`${shortName(name(byAxis.get(kx)?.name ?? kx))} →`);
        svg.append("text").attr("x", 48).attr("y", 13).style("font-size", "13px").style("fill", "var(--ink-soft)")
          .text(`↑ ${shortName(name(byAxis.get(ky)?.name ?? ky))}`);
        const xf = (p: RolePlayer) => x(clamp(p[kx])), yf = (p: RolePlayer) => y(clamp(p[ky]));
        const looks = new Map(pts.map((p) => [p, look(p, pick)]));
        svg.append("g").selectAll("circle").data([...pts].sort((a, b) => looks.get(a)!.front - looks.get(b)!.front)).join("circle")
          .attr("cx", xf).attr("cy", yf).attr("r", (p) => looks.get(p)!.r)
          .style("fill", (p) => looks.get(p)!.color).style("fill-opacity", (p) => looks.get(p)!.alpha)
          .style("stroke", "var(--ink)").style("stroke-opacity", (p) => Math.min(0.9, looks.get(p)!.alpha)).style("stroke-width", 1);
        drawLabels(svg, archLabels((vx, vy) => [x(vx), y(vy)]), w, h, pick, onPick);
        attachHover(svg, el, pts, xf, yf, () => el.clientWidth / w, lines, onPick, dragEnd, onOpen);
        return;
      }
      const [ka, kb, kc] = used, s = Math.min(w, h) / 7.6;
      const { yaw, pitch } = view.current;
      const project = (vx: number, vy: number, vz: number) => {
        const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
        const x1 = vx * cy + vz * sy, z1 = -vx * sy + vz * cy;
        const y1 = vy * cp - z1 * sp, depth = vy * sp + z1 * cp;
        return [w / 2 + x1 * s, h / 2 - y1 * s, depth];
      };
      const ax = svg.append("g");
      ([[ka, [3, 0, 0]], [kb, [0, 3, 0]], [kc, [0, 0, 3]]] as [AxisKey, number[]][]).forEach(([k, v]) => {
        const [x0, y0] = project(-v[0], -v[1], -v[2]), [x1, y1] = project(v[0], v[1], v[2]);
        ax.append("line").attr("x1", x0).attr("y1", y0).attr("x2", x1).attr("y2", y1)
          .style("stroke", "var(--ink)").style("stroke-width", 1.5).style("stroke-dasharray", "4 5");
        ax.append("text").attr("x", x1).attr("y", y1 - 8).attr("text-anchor", "middle").style("font-size", "13px")
          .style("fill", "var(--ink-soft)").text(`${shortName(name(byAxis.get(k)?.name ?? k))} +`);
      });
      const pos = new Map(pts.map((p) => [p, project(clamp(p[ka]), clamp(p[kb]), clamp(p[kc]))]));
      const looks = new Map(pts.map((p) => [p, look(p, pick)]));
      svg.append("g").selectAll("circle").data([...pts].sort((a, b) => pos.get(a)![2] - pos.get(b)![2])).join("circle")
        .attr("cx", (p) => pos.get(p)![0]).attr("cy", (p) => pos.get(p)![1])
        .attr("r", (p) => looks.get(p)!.r * (0.85 + 0.06 * pos.get(p)![2]))
        .style("fill", (p) => looks.get(p)!.color).style("fill-opacity", (p) => looks.get(p)!.alpha)
        .style("stroke", "var(--ink)").style("stroke-opacity", (p) => Math.min(0.9, looks.get(p)!.alpha)).style("stroke-width", 1);
      drawLabels(svg, archLabels((a, b, c) => project(a, b, c)), w, h, pick, onPick);
      attachHover(svg, el, pts, (p) => pos.get(p)![0], (p) => pos.get(p)![1], () => el.clientWidth / w, lines, onPick, dragEnd, onOpen);
    };
    render();

    if (dim === 3) {
      let drag: { x: number; y: number; moved: number } | null = null;
      svg.on("pointerdown", (e: PointerEvent) => { drag = { x: e.clientX, y: e.clientY, moved: 0 }; svgEl.setPointerCapture(e.pointerId); el.style.cursor = "grabbing"; })
        .on("pointermove", (e: PointerEvent) => {
          if (!drag) return;
          const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
          drag = { x: e.clientX, y: e.clientY, moved: drag.moved + Math.abs(dx) + Math.abs(dy) };
          view.current.yaw += dx * 0.01;
          view.current.pitch = Math.max(-1.4, Math.min(1.4, view.current.pitch + dy * 0.01));
          hideTip(el);
          render();
        })
        .on("pointerup pointercancel", () => { if (drag && drag.moved > 3) dragEnd.at = Date.now(); drag = null; el.style.cursor = ""; });
    }
    return () => { svg.on("pointerdown pointermove pointerup pointercancel mousemove mouseleave click", null); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [players, axes, archetypes, pick, set, dim, core, pair, width, theme, lang, includeLow]);

  return (
    <div>
      <div className="row" style={{ marginBottom: 10 }}>
        <div className="seg" role="group" aria-label={t("坐标轴")}>
          <button type="button" aria-pressed={set === "factor"} onClick={() => setSet("factor")}>{t("可解释指数")}</button>
          <button type="button" aria-pressed={set === "lda"} onClick={() => setSet("lda")}>{t("分得最开")}</button>
        </div>
        <div className="seg" role="group" aria-label={t("维度")}>
          <button type="button" aria-pressed={dim === 3} onClick={() => setDim(3)}>3D</button>
          <button type="button" aria-pressed={dim === 2} onClick={() => setDim(2)}>2D</button>
        </div>
        <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>
          <input type="checkbox" checked={core} onChange={(e) => setCore(e.target.checked)} /> {t("只看核心成员（主风格占比 ≥ 50%）")}
        </label>
        {dim === 2 ? (["横轴", "纵轴"] as const).map((ax, i) => (
          <label key={ax} className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t(ax)}
            <select className="select" value={pair[set][i]} onChange={(e) => {
              const next = [...pair[set]] as [AxisKey, AxisKey]; next[i] = e.target.value as AxisKey;
              setPair({ ...pair, [set]: next });
            }}>
              {shown.map((a) => <option key={a.axis} value={a.axis}>{shortName(name(a.name))}</option>)}
            </select>
          </label>
        )) : (
          <button type="button" className="btn" onClick={() => { view.current = { ...VIEW }; setRedraw((n) => n + 1); setDim(2); setTimeout(() => setDim(3)); }}>{t("重置视角")}</button>
        )}
      </div>
      <div ref={box} className="chart"><svg ref={svgRef} role="img" aria-label={t("聚类视图")} /></div>
      <dl className="axis-defs">
        {used.map((k, i) => {
          const a = byAxis.get(k);
          return a ? [<dt key={`t${k}`}>{t(["横轴", "纵轴", "纵深"][i])} · {name(a.name)}</dt>,
            <dd key={`d${k}`}>{t("高：{high}；低：{low}", { high: labelList(a.high, lang), low: labelList(a.low, lang) })}</dd>] : null;
        })}
      </dl>
    </div>
  );
}

/* ---------- style map (t-SNE) ---------- */

export function StyleMap({ players, archetypes, pick, onPick, onOpen, includeLow = false }: {
  players: RolePlayer[]; archetypes: RoleType[]; pick: number | null;
  onPick: (id: number | null) => void; onOpen: (id: number) => void; includeLow?: boolean;
}) {
  const [box, width] = useWidth<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const theme = useThemeTick();
  const { t, name, lang } = useLang();
  useEffect(() => {
    const el = box.current, svgEl = svgRef.current;
    if (!el || !svgEl || !width) return;
    const names = new Map(archetypes.map((a) => [a.type_id, name(a.name)]));
    const pts = players.filter((p) => p.in_fit || includeLow);
    const w = width, h = Math.round(Math.max(340, Math.min(540, w * 0.7)));
    const svg = d3.select(svgEl).attr("viewBox", `0 0 ${w} ${h}`).attr("width", "100%");
    svg.selectAll("*").remove();
    const x = d3.scaleLinear(d3.extent(pts, (p) => p.x) as [number, number], [18, w - 18]);
    const y = d3.scaleLinear(d3.extent(pts, (p) => p.y) as [number, number], [h - 18, 18]);
    const looks = new Map(pts.map((p) => [p, look(p, pick)]));
    svg.append("g").selectAll("circle").data([...pts].sort((a, b) => looks.get(a)!.front - looks.get(b)!.front)).join("circle")
      .attr("cx", (p) => x(p.x)).attr("cy", (p) => y(p.y)).attr("r", (p) => looks.get(p)!.r)
      .style("fill", (p) => looks.get(p)!.color).style("fill-opacity", (p) => looks.get(p)!.alpha)
      .style("stroke", "var(--ink)").style("stroke-opacity", (p) => Math.min(0.9, looks.get(p)!.alpha)).style("stroke-width", 1);
    const labels: Label[] = archetypes.map((a) => {
      const pure = [...pts].sort((p, q) => (q.weights[a.type_id] ?? 0) - (p.weights[a.type_id] ?? 0)).slice(0, 5);
      return { name: name(a.name), id: a.type_id, x: x(d3.median(pure, (p) => p.x)!), y: y(d3.median(pure, (p) => p.y)!) };
    });
    drawLabels(svg, labels, w, h, pick, onPick);
    attachHover(svg, el, pts, (p) => x(p.x), (p) => y(p.y), () => el.clientWidth / w,
      (p) => [["", `${p.name} · ${teamName(p.team, lang)}`], [t("大类"), name(p.family_name)], [t("风格构成"), mixText(p, names)]], onPick, { at: 0 }, onOpen);
  }, [players, archetypes, pick, width, theme, onPick, onOpen, box, lang, t, name, includeLow]);
  return <div ref={box} className="chart"><svg ref={svgRef} role="img" aria-label={t("风格地图")} /></div>;
}

/* ---------- profile heatmap ---------- */

export function ProfileHeatmap({ side, archetypes, families, pick, onPick }: {
  side: Side; archetypes: RoleType[]; families: RoleType[]; pick: number | null; onPick: (id: number | null) => void;
}) {
  const [box, width] = useWidth<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const theme = useThemeTick();
  const { t: tr, name, lang } = useLang();
  useEffect(() => {
    const el = box.current, svgEl = svgRef.current;
    if (!el || !svgEl || !width) return;
    const rows = [...archetypes.map((t) => ({ t, label: name(t.name), arch: true })),
      ...families.map((t) => ({ t, label: tr("大类 · {name}", { name: name(t.name) }), arch: false }))];
    const codes = PROFILE_FEATURES[side].filter((c) => c in (archetypes[0]?.profile ?? {}));
    const lo = cssColor("--seq-lo"), mid = cssColor("--seq-mid"), hi = cssColor("--seq-hi");
    const color = (z: number) => (z >= 0 ? d3.interpolateRgb(mid, hi)(Math.min(z / 2, 1)) : d3.interpolateRgb(mid, lo)(Math.min(-z / 2, 1)));
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    const rl = svg.append("g").selectAll<SVGTextElement, (typeof rows)[number]>("text").data(rows).join("text")
      .text((r) => `${r.label} · ${r.t.n_fit}`).attr("text-anchor", "end").attr("dominant-baseline", "middle")
      .style("font-size", "13px").style("fill", "var(--ink)").style("font-weight", (r) => (r.arch && r.t.type_id === pick ? 700 : 400))
      .style("cursor", (r) => (r.arch ? "pointer" : "default"))
      .on("click", (_e, r) => { if (r.arch) onPick(r.t.type_id === pick ? null : r.t.type_id); });
    const cl = svg.append("g").selectAll<SVGTextElement, string>("text").data(codes).join("text").text((c) => label(c, lang))
      .style("font-size", "12px").style("fill", "var(--muted)");
    let labelW = 0; rl.each(function () { labelW = Math.max(labelW, this.getComputedTextLength()); });
    let headW = 0; cl.each(function () { headW = Math.max(headW, this.getComputedTextLength()); });
    const left = labelW + 30, cw = Math.max(24, Math.floor((width - left - 8) / codes.length)), ch = 26;
    const top = Math.ceil(headW * Math.SQRT1_2) + 14;
    const rowY = (i: number) => top + i * ch + (rows[i].arch ? 0 : 14);
    const W = left + cw * codes.length + Math.ceil(headW * Math.SQRT1_2), H = rowY(rows.length - 1) + ch + 4;
    svg.attr("width", W).attr("height", H).attr("viewBox", `0 0 ${W} ${H}`);
    rl.attr("x", left - 24).attr("y", (_r, i) => rowY(i) + ch / 2);
    svg.append("g").selectAll("circle").data(rows.filter((r) => r.arch)).join("circle")
      .attr("cx", left - 12).attr("cy", (r) => rowY(rows.indexOf(r)) + ch / 2).attr("r", 6)
      .style("fill", (r) => seriesColor(r.t.type_id)).style("stroke", "var(--ink)").style("stroke-width", 1.5);
    cl.attr("transform", (_c, j) => `translate(${left + j * cw + cw / 2},${top - 6}) rotate(-45)`);
    rows.forEach((r, i) => {
      svg.append("g").selectAll("rect").data(codes).join("rect")
        .attr("x", (_c, j) => left + j * cw + 1).attr("y", rowY(i) + 1).attr("width", cw - 2).attr("height", ch - 2)
        .style("fill", (c) => color(r.t.profile[c] ?? 0)).style("stroke", "var(--rule)")
        .style("opacity", pick == null || !r.arch || r.t.type_id === pick ? 1 : 0.3)
        .on("mousemove", (e: MouseEvent, c) => {
          const [mx, my] = d3.pointer(e, el);
          const z = Math.max(-3, Math.min(3, r.t.profile[c] ?? 0));
          const sigma = `${z >= 0 ? "+" : "−"}${Math.abs(z).toFixed(1)}σ`;
          showTip(el, [["", r.label], [label(c, lang), tr(z >= 0 ? "{sigma}，高于联盟平均" : "{sigma}，低于联盟平均", { sigma })]], mx, my);
        })
        .on("mouseleave", () => hideTip(el))
        .on("click", () => { if (r.arch) onPick(r.t.type_id === pick ? null : r.t.type_id); });
    });
  }, [side, archetypes, families, pick, width, theme, onPick, box, lang, tr, name]);
  return (
    <div>
      <div className="row note" style={{ marginBottom: 6 }}>
        <span>{tr("低于平均 −2σ")}</span>
        <span style={{ width: 140, height: 10, border: "2px solid var(--ink)", background: "linear-gradient(to right, var(--seq-lo), var(--seq-mid), var(--seq-hi))" }} />
        <span>{tr("高于平均 +2σ")}</span>
      </div>
      <div ref={box} style={{ overflowX: "auto", position: "relative" }}><svg ref={svgRef} role="img" aria-label={tr("原型画像")} /></div>
    </div>
  );
}
