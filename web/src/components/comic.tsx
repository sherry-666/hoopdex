import { ReactNode, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Power, SeasonInfo, seriesColor } from "../api";
import { POWERS_EN, useLang } from "../i18n";
import { divisionOf, teamName } from "../teams";
import { OffDef, OvrBadge } from "./rating";

/** A team's name as a link to its page; a traded player's "LAL/PHI" links each team. Teams without a page stay plain text. */
export function TeamLink({ team, season, long = false }: { team: string; season?: string; long?: boolean }) {
  const { lang } = useLang();
  return (
    <>
      {team.split("/").map((abbr, i) => (
        <span key={abbr}>
          {i > 0 && " / "}
          {divisionOf(abbr) < 0 ? teamName(abbr, lang, long)
            : <Link to={`/teams/${abbr}${season ? `?season=${season}` : ""}`}>{teamName(abbr, lang, long)}</Link>}
        </span>
      ))}
    </>
  );
}

/** A team's comic emblem: /team-logos/<abbr>.webp when it exists, otherwise nothing. */
export function TeamLogo({ team, size = 28 }: { team: string; size?: number }) {
  const [missing, setMissing] = useState(false);
  if (missing) return null;
  return (
    <img src={`/team-logos/${team}.webp`} alt="" width={size} height={size} onError={() => setMissing(true)}
      style={{ display: "inline-block", width: size, height: size, objectFit: "contain", verticalAlign: "middle", marginRight: 6, flex: "none" }} />
  );
}

/** Players whose portrait also has a short silent clip at /portraits/<id>.mp4. */
const ANIMATED = new Set<number>([201939, 2544]);

function motionAllowed() {
  if (typeof window === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  return !(navigator as { connection?: { saveData?: boolean } }).connection?.saveData;
}

/** The still portrait with its clip laid over it. The clip plays once, then the still shows again: when the pointer
 * enters (hover devices), and when the portrait first comes mostly into view (play="view", or touch devices, which
 * have no hover). When the pointer leaves, it stops at once and the still shows. It is fetched only the first time
 * it is needed. */
function MotionPortrait({ id, alt, size, play, onError }: {
  id: number; alt: string; size: number; play?: "hover" | "view"; onError: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const pending = useRef(false);
  const seen = useRef(false);
  const [armed, setArmed] = useState(false);
  const [ticket, setTicket] = useState(0);
  const [playing, setPlaying] = useState(false);
  const canHover = window.matchMedia("(hover: hover)").matches;
  const onView = play === "view" || !canHover;

  // Ask for one play; the src is attached on the first ask, so the effect below runs the clip.
  const start = () => {
    const v = video.current;
    if (v && !v.paused && !v.ended) return;
    pending.current = true;
    setArmed(true);
    setTicket((n) => n + 1);
  };

  const stop = () => {
    pending.current = false;
    video.current?.pause();
    setPlaying(false);
  };

  useEffect(() => {
    const v = video.current;
    if (!v || !armed || !pending.current) return;
    pending.current = false;
    v.currentTime = 0;
    v.play().catch(() => setPlaying(false));
  }, [armed, ticket]);

  useEffect(() => {
    if (!onView || !box.current) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.intersectionRatio >= 0.6 && !seen.current) { seen.current = true; start(); }
      else if (e.intersectionRatio < 0.2) seen.current = false;
    }, { threshold: [0, 0.2, 0.6] });
    io.observe(box.current);
    return () => io.disconnect();
  }, [onView]);

  return (
    <div ref={box} onPointerEnter={(e) => { if (e.pointerType === "mouse") start(); }}
      onPointerLeave={(e) => { if (e.pointerType === "mouse") stop(); }}
      style={{ position: "relative", border: "var(--line) solid var(--ink)", lineHeight: 0 }}>
      <img src={`/portraits/${id}.webp`} alt={alt} width={size} height={size * 1.2} onError={onError}
        style={{ display: "block", width: "100%", height: "auto", aspectRatio: "5 / 6", objectFit: "cover" }} />
      <video ref={video} src={armed ? `/portraits/${id}.mp4` : undefined} muted playsInline preload="none" aria-hidden="true"
        tabIndex={-1} disablePictureInPicture onPlaying={() => setPlaying(true)} onEnded={() => setPlaying(false)}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", pointerEvents: "none",
          opacity: playing ? 1 : 0 }} />
    </div>
  );
}

/** A player's comic portrait: /portraits/<id>.webp when it exists, otherwise an
 * inked silhouette on halftone in the colour of his main archetype. */
export function Portrait({ id, name, archetype, size = 220, play }: {
  id: number; name: string; archetype?: number | null; size?: number; play?: "hover" | "view";
}) {
  const { t } = useLang();
  const [missing, setMissing] = useState(false);
  const color = archetype == null ? "var(--pop-yellow)" : seriesColor(archetype);
  if (!missing) {
    const alt = t("{name} 的漫画形象", { name });
    if (ANIMATED.has(id) && motionAllowed()) return <MotionPortrait id={id} alt={alt} size={size} play={play} onError={() => setMissing(true)} />;
    return (
      <img src={`/portraits/${id}.webp`} alt={alt} width={size} height={size * 1.2}
        style={{ display: "block", width: "100%", height: "auto", aspectRatio: "5 / 6", objectFit: "cover", border: "var(--line) solid var(--ink)" }}
        onError={() => setMissing(true)} />
    );
  }
  const rays = Array.from({ length: 16 }, (_, i) => (i / 16) * Math.PI * 2);
  return (
    <svg viewBox="0 0 150 180" role="img" aria-label={t("{name}：漫画形象待绘制", { name })}
      style={{ display: "block", width: "100%", height: "auto", border: "var(--line) solid var(--ink)", background: color }}>
      <defs>
        <pattern id={`dots-${id}`} width="7" height="7" patternUnits="userSpaceOnUse">
          <circle cx="3.5" cy="3.5" r="1.5" fill="#000" opacity="0.18" />
        </pattern>
      </defs>
      <rect width="150" height="180" fill={`url(#dots-${id})`} />
      <g stroke="#111" strokeWidth="1.2" opacity="0.35">
        {rays.map((a) => <line key={a} x1="75" y1="80" x2={75 + Math.cos(a) * 160} y2={80 + Math.sin(a) * 160} />)}
      </g>
      <circle cx="75" cy="70" r="26" fill="#fff" stroke="#111" strokeWidth="3" />
      <path d="M28 180 C32 132 52 108 75 108 C98 108 118 132 122 180 Z" fill="#fff" stroke="#111" strokeWidth="3" />
    </svg>
  );
}

export function Burst({ value, label, tone = "red" }: { value: ReactNode; label: string; tone?: "red" | "yellow" | "blue" }) {
  return (
    <div className={`burst pop-in ${tone === "red" ? "" : tone}`}>
      <span className="num">{value}</span>
      <span className="lbl">{label}</span>
    </div>
  );
}

export function MixBar({ mix, height = 14 }: { mix: { id: number; name: string; weight: number }[]; height?: number }) {
  const { name } = useLang();
  return (
    <div className="mixbar" style={{ height }} role="img"
      aria-label={mix.filter((m) => m.weight >= 0.05).map((m) => `${name(m.name)} ${Math.round(m.weight * 100)}%`).join(", ")}>
      {mix.filter((m) => m.weight >= 0.02).map((m) => (
        <span key={m.id} title={`${name(m.name)} ${Math.round(m.weight * 100)}%`} style={{ width: `${m.weight * 100}%`, background: seriesColor(m.id) }} />
      ))}
    </div>
  );
}

const PCT_FEATURES = /share|pct|rate|_pt_|^shot_/;

export function PowerBubble({ power, label }: { power: Power; label: string }) {
  const { t, lang } = useLang();
  const fmt = (v: number) => (PCT_FEATURES.test(power.feature) ? `${(v * 100).toFixed(1)}%` : v.toFixed(2));
  const [title, desc] = lang === "en" && POWERS_EN[power.feature] ? POWERS_EN[power.feature] : [power.name, power.description];
  return (
    <div className="bubble pop-in" style={{ marginBottom: 16 }}>
      <div className="row" style={{ gap: 10, flexWrap: "nowrap", alignItems: "flex-start" }}>
        <span className={`grade ${power.grade}`} aria-label={t("等级 {g}", { g: power.grade })}>{power.grade}</span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontFamily: lang === "en" ? "var(--font-latin)" : "var(--font-display)", fontSize: lang === "en" ? 24 : 20, letterSpacing: lang === "en" ? 0.5 : 0, lineHeight: 1.2 }}>{title}</div>
          <div style={{ fontSize: "var(--size-body)" }}>{desc}</div>
          <div className="note">
            {t("依据：{label} {value}，高于联盟平均 {z} 个标准差", { label, value: power.value == null ? "" : fmt(power.value), z: power.z.toFixed(1) })}
          </div>
        </div>
      </div>
    </div>
  );
}

export function PlayerCard({ id, name, team, style, archetype, season, ovr, off, def, extra }: {
  id: number; name: string; team: string; style?: string | null; archetype?: number | null; season?: string;
  ovr?: number | null; off?: number | null; def?: number | null; extra?: ReactNode;
}) {
  const lang = useLang();
  return (
    <Link to={season ? `/players/${id}?season=${season}` : `/players/${id}`} className="panel pop-in" style={{ display: "flex", flexDirection: "column", gap: 8, textDecoration: "none", padding: 10 }}>
      <div style={{ position: "relative" }}>
        <Portrait id={id} name={name} archetype={archetype} />
        <span style={{ position: "absolute", top: 8, right: 8 }}><OvrBadge ovr={ovr} /></span>
      </div>
      <div style={{ fontFamily: "var(--font-latin)", fontSize: 22, letterSpacing: 0.5, lineHeight: 1 }}>{name}</div>
      <div className="row" style={{ gap: 6 }}>
        <span className="tag">{teamName(team, lang.lang)}</span>
        {style && <span className="note" style={{ color: "var(--ink-soft)" }}>{lang.name(style)}</span>}
      </div>
      <OffDef off={off} def={def} size={13} />
      {extra}
    </Link>
  );
}

/** Season dropdown; seasons still in progress are marked as such. */
export function SeasonSelect({ value, seasons, onChange }: {
  value: string | undefined; seasons: SeasonInfo[] | string[] | undefined; onChange: (s: string) => void;
}) {
  const { t } = useLang();
  const infos = (seasons ?? []).map((s) => (typeof s === "string" ? { season: s, in_progress: false } : s));
  return (
    <label className="row" style={{ gap: 6, fontSize: "var(--size-caption)" }}>{t("赛季")}
      <select className="select" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {infos.map((s) => (
          <option key={s.season} value={s.season}>{s.in_progress ? t("{season}（进行中）", { season: s.season }) : s.season}</option>
        ))}
      </select>
    </label>
  );
}

export function Loading({ what = "数据" }: { what?: string }) {
  const { t } = useLang();
  return <div className="panel halftone" style={{ minHeight: 160, display: "grid", placeItems: "center" }}><span className="caption">{t("正在加载{what}……", { what: t(what) })}</span></div>;
}

export function Failed({ error }: { error: unknown }) {
  const { t } = useLang();
  return (
    <div className="panel" style={{ borderColor: "var(--pop-red)" }}>
      <span className="caption" style={{ background: "var(--pop-red)", color: "#fff" }}>{t("出错了")}</span>
      <p style={{ marginTop: 12 }}>{t("数据没能加载：{msg}。检查 API 服务（端口 8000）是否在运行，然后刷新。", { msg: t(String((error as Error)?.message ?? error)) })}</p>
    </div>
  );
}
