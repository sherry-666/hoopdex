"""Generate original American-comic superhero emblems for the 30 NBA teams.

Each emblem is an abstract chest-badge in the portrait style (thick black outline, flat colour,
halftone shading) built from the team's nickname and colours. No real team logo, no text.

    python scripts/gen_team_logos.py            # writes web/public/team-logos/<ABBR>.svg
"""
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "team-logos"
K = "#111"
W = "#fff"


def pt(cx, cy, r, deg):
    a = math.radians(deg - 90)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def poly(points):
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points) + " Z"


def star(cx, cy, n, ro, ri, rot=0):
    pts = []
    for i in range(n * 2):
        pts.append(pt(cx, cy, ro if i % 2 == 0 else ri, rot + i * 180 / n))
    return poly(pts)


def gear(cx, cy, n, ro, ri, tw=7):
    pts = []
    for i in range(n):
        t = i * 360 / n
        pts += [pt(cx, cy, ri, t - tw * 1.7), pt(cx, cy, ro, t - tw), pt(cx, cy, ro, t + tw), pt(cx, cy, ri, t + tw * 1.7)]
    return poly(pts)


def P(d, fill, sw=5):
    return f'<path d="{d}" fill="{fill}" stroke="{K}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"/>'


def C(cx, cy, r, fill, sw=5):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{K}" stroke-width="{sw}"/>'


def E(cx, cy, rx, ry, fill, sw=5, rot=0):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{K}" stroke-width="{sw}" transform="rotate({rot} {cx} {cy})"/>'


def R(x, y, w, h, fill, sw=5):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{K}" stroke-width="{sw}" stroke-linejoin="round"/>'


def fat(d, color, w=8, edge=5):
    """Thick outlined stroke."""
    return (f'<path d="{d}" fill="none" stroke="{K}" stroke-width="{w + edge * 2}" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')


def mirror(inner):
    return f'<g transform="translate(200,0) scale(-1,1)">{inner}</g>'


def sym(inner):
    return inner + mirror(inner)


def sparkle(cx, cy, r, fill=W):
    d = f"M{cx} {cy - r} Q{cx} {cy} {cx + r} {cy} Q{cx} {cy} {cx} {cy + r} Q{cx} {cy} {cx - r} {cy} Q{cx} {cy} {cx} {cy - r} Z"
    return P(d, fill, 3)


# ---------------------------------------------------------------- glyphs
def g_ATL():
    wing = P("M96 142 L22 56 L64 70 L38 94 L76 96 L54 122 L92 120 Z", "#F2F2F2")
    return (sym(wing)
            + P("M72 70 Q100 40 128 70 L120 112 Q100 128 80 112 Z", "#E03A3E")
            + P("M86 104 L100 142 L114 104 Z", "#C1D32F")
            + P("M80 84 L96 90 L92 98 L78 92 Z", W, 3) + P("M120 84 L104 90 L108 98 L122 92 Z", W, 3))


def g_BOS():
    heart = "M0 0 C-30 -22 -30 -54 -14 -54 C-6 -54 0 -47 0 -40 C0 -47 6 -54 14 -54 C30 -54 30 -22 0 0 Z"
    leaves = "".join(f'<g transform="translate(100 96) rotate({a})">{P(heart, W)}<path d="M0 -6 L0 -38" stroke="#007A33" stroke-width="4" stroke-linecap="round"/></g>' for a in (0, 120, 240))
    return leaves + fat("M100 96 C100 128 108 144 124 152", W, 6) + C(100, 96, 7, "#BA9653", 4)


def g_BKN():
    clip = "M100 26 L162 88 L100 150 L38 88 Z"
    lines = "".join(f'<path d="M{x} 20 L{x + 120} 160 M{x + 120} 20 L{x} 160" stroke="{K}" stroke-width="3"/>' for x in range(-20, 140, 28))
    return (f'<clipPath id="nt"><path d="{clip}"/></clipPath>' + P(clip, W)
            + f'<g clip-path="url(#nt)">{lines}</g>' + f'<path d="{clip}" fill="none" stroke="{K}" stroke-width="6"/>'
            + P("M100 150 L100 172", K, 6) + P("M82 150 Q100 170 118 150", "#8d8d8d", 4))


def g_CHA():
    wing = P("M92 84 C60 40 30 52 36 84 C42 108 76 104 92 96 Z", "#cfe9ee")
    body = "".join(P(f"M{100 - w} {y} L{100 + w} {y} L{100 + w - 3} {y + 14} L{100 - w + 3} {y + 14} Z", c, 4)
                   for (w, y, c) in ((20, 92, "#00788C"), (18, 106, "#1D1160"), (15, 120, "#00788C"), (11, 134, "#1D1160")))
    return (sym(wing) + body + P("M92 148 L100 176 L108 148 Z", "#F5C518", 4)
            + C(100, 70, 22, "#00788C") + P("M82 62 L96 70 L88 78 Z", "#F5C518", 3) + P("M118 62 L104 70 L112 78 Z", "#F5C518", 3))


def g_CHI():
    horn = P("M24 46 C28 92 62 106 84 98 L84 82 C62 84 46 70 42 44 Z", W)
    return (sym(horn)
            + P("M70 78 L130 78 L118 146 Q100 162 82 146 Z", K)
            + P("M78 96 L96 102 L90 110 Z", "#CE1141", 3) + P("M122 96 L104 102 L110 110 Z", "#CE1141", 3)
            + E(100, 138, 14, 9, "#CE1141", 4) + P("M84 118 Q100 126 116 118", "none", 4).replace('stroke="#111"', 'stroke="#fff"'))


def g_CLE():
    rays = "".join(f'<path d="M100 96 L{pt(100, 96, 70, a)[0]:.1f} {pt(100, 96, 70, a)[1]:.1f}" stroke="#FFB81C" stroke-width="5" stroke-linecap="round"/>' for a in range(-80, 100, 20) if a != 0)
    return (rays + P("M100 24 L113 40 L113 118 L87 118 L87 40 Z", "#dfe5ea")
            + '<path d="M100 38 L100 114" stroke="#9aa6b0" stroke-width="4"/>'
            + P("M58 118 L142 118 L134 134 L66 134 Z", "#FFB81C") + R(93, 134, 14, 22, "#4a1a2b", 4) + C(100, 164, 9, "#FFB81C", 4))


def g_DAL():
    shoe = "M52 36 L52 110 Q52 160 100 160 Q148 160 148 110 L148 36 L122 36 L122 108 Q122 134 100 134 Q78 134 78 108 L78 36 Z"
    holes = "".join(C(x, y, 4, "#00538C", 3) for x, y in ((65, 60), (65, 88), (135, 60), (135, 88), (84, 138 - 4), (116, 134)))
    return P(shoe, "#C0CAD0") + holes + P(star(100, 86, 5, 24, 10), "#FFC72C")


def g_DEN():
    peaks = P("M20 146 L76 54 L102 98 L122 68 L180 146 Z", "#8BB8E8")
    snow = P("M76 54 L62 78 L72 74 L80 84 L90 72 Z", W, 4) + P("M122 68 L111 86 L120 84 L126 90 L133 82 Z", W, 4)
    gem = P("M100 104 L128 114 L136 140 L110 160 L84 144 L84 116 Z", "#FEC524")
    facets = '<path d="M100 104 L110 160 M84 116 L128 114 M84 144 L136 140" stroke="#111" stroke-width="3" fill="none"/>'
    return peaks + snow + gem + facets


def g_DET():
    return (P(gear(100, 96, 8, 66, 50), "#C0CAD0") + C(100, 96, 34, "#C8102E") + C(100, 96, 17, "#1D42BA")
            + P("M104 78 L88 100 L99 100 L94 116 L112 92 L101 92 Z", W, 3))


def g_GSW():
    sun = C(100, 84, 38, "#7fa6ff", 4)
    waves = "".join(f'<path d="M{44 + i * 36} {154 + j * 12} q9 -9 18 0 t18 0" stroke="#FFC72C" stroke-width="4" fill="none"/>' for i in range(3) for j in (0, 1))
    return (sun + fat("M20 128 Q50 126 69 50 Q100 128 131 50 Q150 126 180 128", "#FFC72C", 5, 3)
            + R(58, 46, 22, 98, "#FFC72C", 4) + R(120, 46, 22, 98, "#FFC72C", 4)
            + R(58, 66, 22, 5, K, 2) + R(120, 66, 22, 5, K, 2) + R(58, 92, 22, 5, K, 2) + R(120, 92, 22, 5, K, 2)
            + R(20, 128, 160, 10, "#fff", 4) + waves)


def g_HOU():
    rocket = (P("M90 130 Q100 178 110 130 Z", "#FFB400") + P("M94 130 Q100 158 106 130 Z", "#fff", 3)
              + sym(P("M84 96 L56 138 L84 128 Z", K)) + P("M100 24 C128 54 128 104 116 130 L84 130 C72 104 72 54 100 24 Z", W)
              + P("M100 24 C112 38 118 50 120 60 L80 60 C82 50 88 38 100 24 Z", "#C8102E", 4) + C(100, 88, 11, "#4aa3df"))
    return f'<g transform="rotate(35 100 100)">{rocket}</g>'


def g_IND():
    def chev(dx, col):
        return P(f"M{34 + dx} 50 L{86 + dx} 100 L{34 + dx} 150 L{34 + dx} 124 L{58 + dx} 100 L{34 + dx} 76 Z", col)
    return chev(0, "#FDBB30") + chev(34, W) + chev(68, "#FDBB30") + "".join(
        f'<path d="M{18} {88 + i * 12} L{36} {88 + i * 12}" stroke="#FDBB30" stroke-width="4" stroke-linecap="round"/>' for i in range(2))


def g_LAC():
    return (P("M100 26 L100 108 L50 108 Z", W) + P("M108 40 L108 108 L150 108 Z", W)
            + P("M70 108 L96 108 L96 70 Z", "#C8102E", 3)
            + P("M44 114 L156 114 L138 144 L62 144 Z", "#1D428A")
            + '<path d="M46 160 q9 -9 18 0 t18 0 t18 0 t18 0 t18 0 t18 0" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round"/>')


def g_LAL():
    rays = P(star(100, 92, 14, 70, 42), "#FDB927")
    return (rays + C(100, 92, 30, "#FFE08A") + C(100, 92, 17, "#FDB927", 4)
            + "".join(f'<path d="M52 {146 + i * 12} q12 -10 24 0 t24 0 t24 0 t24 0" stroke="{c}" stroke-width="5" fill="none" stroke-linecap="round"/>' for i, c in enumerate((W, "#FDB927"))))


def g_MEM():
    claws = "".join(P(f"M{x} {y} q{dx} -16 {dx * 2} -18 q-2 12 {-dx} 18 Z", W, 3) for x, y, dx in ((54, 62, -6), (84, 40, -2), (116, 40, 2), (146, 62, 6)))
    toes = "".join(E(x, y, 13, 17, "#12173F", 5, rot=r) for x, y, r in ((52, 80, -25), (82, 56, -8), (118, 56, 8), (148, 80, 25)))
    pad = P("M100 90 C132 90 156 118 148 140 C142 158 118 150 100 150 C82 150 58 158 52 140 C44 118 68 90 100 90 Z", "#12173F")
    hl = '<path d="M72 112 Q84 100 100 100" stroke="#5D76A9" stroke-width="5" fill="none" stroke-linecap="round"/>'
    return toes + pad + hl


def g_MIA():
    outer = P("M100 22 C110 56 152 70 150 114 C148 148 126 168 100 168 C74 168 52 148 52 114 C52 88 72 76 80 50 C88 66 90 72 94 72 C94 56 96 40 100 22 Z", "#F9A01B")
    mid = P("M102 70 C108 92 134 100 132 124 C130 146 116 156 100 156 C84 156 70 146 70 124 C70 108 84 100 90 86 C94 96 98 98 100 98 Z", "#E03A1E", 4)
    core = P("M100 112 C106 124 118 128 116 140 C114 150 108 152 100 152 C92 152 86 150 86 140 C86 130 96 126 100 112 Z", "#FFE08A", 3)
    return outer + mid + core


def g_MIL():
    antler = (fat("M80 118 L46 112", W, 6, 4) + fat("M68 94 L38 80", W, 6, 4) + fat("M62 76 L60 46", W, 6, 4)
              + fat("M98 150 C84 116 58 102 44 56", W, 10, 4))
    return (sym(antler) + P("M100 62 L108 82 L130 84 L113 98 L119 120 L100 108 L81 120 L87 98 L70 84 L92 82 Z", "#EEE1C6", 4).replace("#EEE1C6", "#E8B923")
            + P("M82 142 L118 142 L108 166 L92 166 Z", W, 4))


def g_MIN():
    face = P("M50 34 L78 68 L122 68 L150 34 L158 100 L122 152 L100 166 L78 152 L42 100 Z", "#9BA9B5")
    inner_ear = sym(P("M54 50 L74 74 L56 88 Z", "#0C2340", 3))
    eyes = sym(P("M66 98 L92 100 L84 112 Z", "#78BE20", 3))
    muzzle = P("M82 122 L118 122 L100 156 Z", W, 4) + P("M91 128 L109 128 L100 140 Z", K, 3)
    return face + inner_ear + eyes + muzzle


def g_NOP():
    petal = P("M100 24 C126 50 124 86 100 114 C76 86 74 50 100 24 Z", "#C7A44A")
    side = P("M94 104 C66 70 30 78 36 114 C54 100 72 104 86 126 Z", "#C7A44A")
    tail = P("M100 140 C92 154 82 160 68 160 C84 170 96 168 100 152 C104 168 116 170 132 160 C118 160 108 154 100 140 Z", "#C7A44A")
    return mirror(side) + side + petal + R(70, 118, 60, 14, "#C8102E", 4) + tail


def g_NYK():
    sun = C(100, 92, 48, "#F58426")
    bs = [(32, 24, 112), (58, 24, 82), (84, 32, 56), (118, 24, 86), (144, 26, 116)]
    b = "".join(R(x, y, w, 150 - y, K, 4) for x, w, y in bs)
    win = "".join(f'<rect x="{x + 6 + i * 9}" y="{y + 12 + j * 14}" width="4" height="6" fill="#F58426"/>' for x, w, y in bs for i in range(max(1, (w - 8) // 9)) for j in range(max(0, (150 - y - 20) // 14)))
    spire = '<path d="M100 56 L100 30" stroke="#111" stroke-width="5" stroke-linecap="round"/>'
    return sun + b + win + spire + R(24, 150, 152, 8, W, 4)


def g_OKC():
    cloud = P("M52 92 Q36 92 38 72 Q40 54 62 56 Q70 32 98 36 Q124 34 132 56 Q160 52 160 76 Q160 94 138 92 Z", "#34495e")
    hl = '<path d="M56 78 Q60 66 74 64" stroke="#7f98ad" stroke-width="5" fill="none" stroke-linecap="round"/>'
    bolt = P("M114 78 L74 124 L98 124 L84 172 L130 110 L106 110 Z", "#EF3B24") + P("M110 92 L90 118 L102 118 L96 140 L116 110 L104 110 Z", "#FFD23F", 0)
    return bolt + cloud + hl


def g_ORL():
    ball = C(100, 82, 46, "#9fd4ff") + '<path d="M66 64 Q74 46 94 42" stroke="#fff" stroke-width="6" fill="none" stroke-linecap="round"/>'
    stand = P("M60 154 L140 154 L126 124 L74 124 Z", "#2b2f36") + R(56, 154, 88, 12, "#C4CED4", 4)
    return ball + sparkle(104, 86, 26) + sparkle(76, 100, 10) + stand + sparkle(158, 40, 12, "#fff") + sparkle(42, 54, 9, "#fff")


def g_PHI():
    bell = P("M100 28 Q106 28 106 36 C142 44 148 90 150 122 L162 134 L162 142 L38 142 L38 134 L50 122 C52 90 58 44 94 36 Q94 28 100 28 Z", "#F0C84B")
    crack = '<path d="M104 40 L94 68 L108 90 L96 118 L104 142" stroke="#ED174C" stroke-width="5" fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
    shine = '<path d="M62 118 C64 90 68 66 80 54" stroke="#fff6cf" stroke-width="6" fill="none" stroke-linecap="round"/>'
    return bell + shine + crack + C(100, 156, 11, "#7a4a1a") + "".join(sparkle(x, y, 8) for x, y in ((40, 56), (162, 60)))


def g_PHX():
    t = [P("M84 92 C66 84 46 68 30 40 C58 42 74 56 90 80 Z", "#E56020"), P("M82 108 C60 108 38 100 22 84 C48 76 68 84 86 98 Z", "#F98A2A"),
         P("M84 122 C68 126 50 128 34 124 C50 112 68 110 86 114 Z", "#FDB927")]
    return (sym("".join(t)) + P(star(100, 100, 12, 42, 28), "#FDB927") + C(100, 100, 24, "#E56020") + C(100, 100, 11, "#FFE08A", 4)
            + P("M90 138 Q100 176 110 138 Z", "#E56020", 4))


def g_POR():
    axe = (R(94, 44, 12, 124, "#7a4a1a", 4)
           + P("M106 46 C148 40 166 72 152 104 C142 88 126 84 106 90 Z", "#C4CED4")
           + '<path d="M114 56 C136 54 148 66 150 80" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/>')
    pines = "".join(P(f"M{x} 160 L{x + 11} 138 L{x + 5} 138 L{x + 14} 118 L{x + 5} 118 L{x} 104 L{x - 5} 118 L{x - 14} 118 L{x - 5} 138 L{x - 11} 138 Z", "#1f6f3a", 3) for x in (46, 154))
    return pines + f'<g transform="rotate(-30 100 100)">{axe}</g>' + sparkle(50, 56, 11, "#E03A3E")


def g_SAC():
    crown = P("M42 132 L36 64 L72 92 L100 50 L128 92 L164 64 L158 132 Z", "#F5C84B")
    band = R(42, 132, 116, 16, "#C4CED4", 4)
    gems = C(100, 100, 9, "#E03A3E", 4) + C(66, 118, 6, "#4aa3df", 3) + C(134, 118, 6, "#4aa3df", 3)
    orbs = "".join(C(x, y, 8, "#F5C84B", 4) for x, y in ((36, 62), (100, 46), (164, 62)))
    return crown + band + gems + orbs


def g_SAS():
    return P(star(100, 96, 14, 72, 40), "#C4CED4") + C(100, 96, 32, K) + P(star(100, 96, 5, 22, 9), "#C4CED4", 3)


def g_TOR():
    halo = C(100, 96, 66, K, 0)
    big = P("M58 30 C140 36 174 112 126 168 C142 114 116 74 58 30 Z", W)
    small = P("M32 68 C82 78 104 120 88 160 C82 124 60 96 32 68 Z", "#d6d6d6")
    return halo + '<circle cx="100" cy="96" r="66" fill="#CE1141" opacity=".5"/>' + small + big + sparkle(142, 52, 10, "#FFD23F")


def g_UTA():
    mnt = P("M22 150 L74 70 L100 108 L124 80 L178 150 Z", "#6aa0d6") + P("M74 70 L62 88 L72 84 L80 92 L88 82 Z", W, 4)
    note = P("M104 56 C124 64 148 76 142 114 C140 96 126 88 104 88 Z", "#F9A01B") + R(98, 56, 10, 86, "#F9A01B", 4) + E(80, 142, 26, 18, "#F9A01B", 5, -20)
    arcs = "".join(f'<path d="M{148 + i * 10} {126 - i * 10} q{8} {10} 0 {20 + i * 4}" stroke="#F9A01B" stroke-width="4" fill="none" stroke-linecap="round"/>' for i in range(2))
    return mnt + note + arcs


def g_WAS():
    hat = P("M96 22 Q122 36 120 66 L136 122 L64 122 L80 70 Q86 50 96 22 Z", "#E31837")
    hat2 = P("M96 22 Q118 24 124 40 Q110 32 98 34 Z", "#E31837", 4)
    brim = E(100, 128, 62, 15, "#E31837")
    band = P("M70 108 Q100 118 130 108 L134 122 Q100 132 66 122 Z", "#F5F5F5", 4)
    return brim + hat + hat2 + band + P(star(98, 78, 5, 11, 5), "#F5C84B", 3) + P(star(112, 52, 5, 7, 3), "#F5C84B", 2) + sparkle(46, 56, 11) + sparkle(156, 66, 9)


GLYPHS = {k[2:]: v for k, v in globals().items() if k.startswith("g_")}

# abbr: (zh, en, frame, base, rim, concept)
TEAMS = {
    "ATL": ("老鹰", "Hawks", "pent", "#1d1d1f", "#E03A3E", "俯冲的猎鹰：双翼如利刃展开，喙尖荧光黄"),
    "BOS": ("凯尔特人", "Celtics", "shield", "#007A33", "#ffffff", "三叶幸运草：三片叶如盾徽，翠绿与白"),
    "BKN": ("篮网", "Nets", "circle", "#111111", "#ffffff", "菱形织网：黑白网格，自带罗网的猎手"),
    "CHA": ("黄蜂", "Hornets", "circle", "#1D1160", "#00788C", "黄蜂战士：青紫条纹腹部，尾针蓄势"),
    "CHI": ("公牛", "Bulls", "pent", "#CE1141", "#111111", "暴怒公牛：弯月牛角、赤红双眼"),
    "CLE": ("骑士", "Cavaliers", "shield", "#6F263D", "#FFB81C", "圣骑士之剑：金色护手，辐射光芒"),
    "DAL": ("独行侠", "Mavericks", "circle", "#00538C", "#C0CAD0", "孤胆牛仔：银色马蹄铁托起金星"),
    "DEN": ("掘金", "Nuggets", "shield", "#0E2240", "#FEC524", "高原之巅：雪山 + 一块切面金矿"),
    "DET": ("活塞", "Pistons", "hex", "#1D42BA", "#C8102E", "机械战甲：钢制齿轮，红色能量核心"),
    "GSW": ("勇士", "Warriors", "shield", "#1D428A", "#FFC72C", "金色大桥：悬索与双塔，守护湾区"),
    "HOU": ("火箭", "Rockets", "burst", "#CE1141", "#C4CED4", "星际火箭：斜向升空，尾焰爆裂"),
    "IND": ("步行者", "Pacers", "hex", "#002D62", "#FDBB30", "赛道急速：三层金白箭头，速度线"),
    "LAC": ("快船", "Clippers", "hex", "#C8102E", "#1D428A", "快速帆船：双帆破浪，蓝色船身"),
    "LAL": ("湖人", "Lakers", "circle", "#552583", "#FDB927", "湖面旭日：十四道金色日冕，王者之光"),
    "MEM": ("灰熊", "Grizzlies", "hex", "#5D76A9", "#12173F", "巨熊之掌：深蓝肉垫，四道白爪"),
    "MIA": ("热火", "Heat", "burst", "#98002E", "#F9A01B", "烈焰火球：三层火焰，由外至内渐亮"),
    "MIL": ("雄鹿", "Bucks", "shield", "#00471B", "#EEE1C6", "森林之王：奶白鹿角，额间金星"),
    "MIN": ("森林狼", "Timberwolves", "shield", "#0C2340", "#78BE20", "夜行狼首：灰面、荧绿双瞳"),
    "NOP": ("鹈鹕", "Pelicans", "shield", "#0C2340", "#C8102E", "鸢尾徽章：金色百合花，红带束腰"),
    "NYK": ("尼克斯", "Knicks", "hex", "#006BB6", "#F58426", "不夜城：橙色落日前的摩天楼天际线"),
    "OKC": ("雷霆", "Thunder", "burst", "#007AC1", "#EF3B24", "雷暴：乌云里劈下橙红闪电"),
    "ORL": ("魔术", "Magic", "circle", "#0077C0", "#C4CED4", "魔法水晶球：球心星芒闪烁"),
    "PHI": ("76人", "76ers", "shield", "#006BB6", "#ED174C", "自由钟：金钟带红色裂纹"),
    "PHX": ("太阳", "Suns", "burst", "#1D1160", "#E56020", "火凤凰：日轮为心，烈焰为翼"),
    "POR": ("开拓者", "Trail Blazers", "hex", "#111111", "#E03A3E", "开拓之斧：松林间的银刃利斧"),
    "SAC": ("国王", "Kings", "shield", "#5A2D81", "#63727A", "王冠：金冠、宝石与银环"),
    "SAS": ("马刺", "Spurs", "circle", "#111111", "#C4CED4", "马刺齿轮：银色刺轮，中央一颗星"),
    "TOR": ("猛龙", "Raptors", "pent", "#CE1141", "#111111", "迅猛龙之爪：两道镰刀利爪撕裂红光"),
    "UTA": ("爵士", "Jazz", "circle", "#002B5C", "#F9A01B", "山间爵士：金色音符 + 雪山，声波外扩"),
    "WAS": ("奇才", "Wizards", "circle", "#002B5C", "#E31837", "魔法师帽：红帽、星辰与闪光"),
}

FRAMES = {
    "shield": ("M100 8 L184 28 L184 100 Q184 160 100 194 Q16 160 16 100 L16 28 Z", "translate(100 100) scale(.93) translate(-100 -100) translate(0 -2)"),
    "circle": ("M100 10 a90 90 0 1 0 .01 0 Z", "translate(100 100) scale(.88) translate(-100 -100)"),
    "hex": ("M100 8 L180 52 L180 148 L100 192 L20 148 L20 52 Z", "translate(100 100) scale(.9) translate(-100 -100)"),
    "pent": ("M18 14 L182 14 L182 108 L100 192 L18 108 Z", "translate(100 100) scale(.9) translate(-100 -100) translate(0 -4)"),
}


def burst_path():
    return star(100, 100, 12, 96, 76, rot=15)


def svg(abbr):
    zh, en, frame, base, rim, concept = TEAMS[abbr]
    if frame == "burst":
        d, glyph_tf = burst_path(), "translate(100 100) scale(.78) translate(-100 -100)"
    else:
        d, glyph_tf = FRAMES[frame]
    uid = abbr.lower()
    inset = f'transform="translate(100 100) scale(.89) translate(-100 -100)"'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" role="img" aria-label="{en}">
<title>{en}</title>
<defs>
<clipPath id="f{uid}"><path d="{d}"/></clipPath>
<pattern id="h{uid}" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(30)"><circle cx="4.5" cy="4.5" r="1.9" fill="#000"/></pattern>
<linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset=".45" stop-color="#000"/><stop offset="1" stop-color="#fff"/></linearGradient>
<mask id="m{uid}"><rect width="200" height="200" fill="url(#g{uid})"/></mask>
</defs>
<path d="{d}" fill="{base}" stroke="{K}" stroke-width="7" stroke-linejoin="round"/>
<g clip-path="url(#f{uid})">
<rect width="200" height="200" fill="url(#h{uid})" mask="url(#m{uid})" opacity=".35"/>
<path d="M0 0 H200 V60 Q100 30 0 80 Z" fill="#fff" opacity=".10"/>
</g>
<path d="{d}" fill="none" stroke="{rim}" stroke-width="4" {inset} stroke-linejoin="round"/>
<path d="{d}" fill="none" stroke="{K}" stroke-width="7" stroke-linejoin="round"/>
<g transform="{glyph_tf}">{GLYPHS[abbr]()}</g>
</svg>
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for abbr in TEAMS:
        (OUT / f"{abbr}.svg").write_text(svg(abbr), encoding="utf-8")
    print(f"wrote {len(TEAMS)} svgs to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
