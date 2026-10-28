"""Server-rendered head and fallback content for search engines and link previews.

The web app renders in the browser, so crawlers that don't run JavaScript would see the
same empty page everywhere. For each route the API fills index.html with that page's
title, description, canonical URL, hreflang alternates, Open Graph / Twitter tags and
JSON-LD, and puts a plain-text summary inside #root. React replaces that summary on mount.

Chinese is the default language; ?lang=en is the English version of any page.
"""

import html
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlencode

SITE_NAME = "Hoopedia"
LANGS = ("zh", "en")
HTML_LANG = {"zh": "zh-CN", "en": "en"}
OG_LOCALE = {"zh": "zh_CN", "en": "en_US"}

SITE_TITLE = {"zh": "Hoopedia · NBA 球员图鉴：打法原型、超能力与数据",
              "en": "Hoopedia · NBA Player Encyclopedia: archetypes, superpowers and stats"}
SITE_DESC = {
    "zh": "Hoopedia 用逐回合和追踪数据，把每名 NBA 球员的打法拆成原型混合，附 2K 式能力值、超能力和生涯数据。",
    "en": "Hoopedia breaks every NBA player's game into archetypes using play-by-play and tracking data, "
          "with 2K-style ratings, superpowers and career stats.",
}

# Mirrors web/src/teams.ts and NAMES_EN in web/src/i18n.tsx.
TEAMS = {
    "ATL": ("老鹰", "Atlanta Hawks"), "BOS": ("凯尔特人", "Boston Celtics"), "BKN": ("篮网", "Brooklyn Nets"),
    "CHA": ("黄蜂", "Charlotte Hornets"), "CHI": ("公牛", "Chicago Bulls"), "CLE": ("骑士", "Cleveland Cavaliers"),
    "DAL": ("独行侠", "Dallas Mavericks"), "DEN": ("掘金", "Denver Nuggets"), "DET": ("活塞", "Detroit Pistons"),
    "GSW": ("勇士", "Golden State Warriors"), "HOU": ("火箭", "Houston Rockets"), "IND": ("步行者", "Indiana Pacers"),
    "LAC": ("快船", "LA Clippers"), "LAL": ("湖人", "Los Angeles Lakers"), "MEM": ("灰熊", "Memphis Grizzlies"),
    "MIA": ("热火", "Miami Heat"), "MIL": ("雄鹿", "Milwaukee Bucks"), "MIN": ("森林狼", "Minnesota Timberwolves"),
    "NOP": ("鹈鹕", "New Orleans Pelicans"), "NYK": ("尼克斯", "New York Knicks"), "OKC": ("雷霆", "Oklahoma City Thunder"),
    "ORL": ("魔术", "Orlando Magic"), "PHI": ("76人", "Philadelphia 76ers"), "PHX": ("太阳", "Phoenix Suns"),
    "POR": ("开拓者", "Portland Trail Blazers"), "SAC": ("国王", "Sacramento Kings"), "SAS": ("马刺", "San Antonio Spurs"),
    "TOR": ("猛龙", "Toronto Raptors"), "UTA": ("爵士", "Utah Jazz"), "WAS": ("奇才", "Washington Wizards"),
}
NAMES_EN = {
    "单打得分手": "Iso Scorer", "突破组织": "Drive-and-Dish Creator", "定点射手": "Spot-up Shooter",
    "无球射手": "Movement Shooter", "内线组织者": "Interior Hub", "挡拆发起者": "Pick-and-Roll Engine",
    "篮下终结者": "Rim Finisher", "追防与被针对": "Chaser / Targeted", "外线防投手": "Perimeter Contester",
    "护框": "Rim Protector", "抢断干扰": "Disruptor",
}


STYLE_EN = {"外线单打": "Perimeter Iso", "跑动传切": "Motion Offense", "内线枢纽": "Interior Hub Offense",
            "冲击转换": "Drive and Run", "持球挡拆": "Ball-screen Creator"}


def team_name(abbr: str | None, lang: str) -> str:
    if not abbr:
        return ""
    names = TEAMS.get(abbr)
    return names[0 if lang == "zh" else 1] if names else abbr


def role_name(zh: str | None, lang: str) -> str:
    if not zh:
        return ""
    return zh if lang == "zh" else " + ".join(NAMES_EN.get(p, p) for p in zh.split(" + "))


@dataclass
class Page:
    status: int
    title: str
    description: str
    path: str                       # canonical path, without lang
    query: dict = field(default_factory=dict)   # canonical query, without lang
    index: bool = True
    image: str | None = None        # site-relative image path
    og_type: str = "website"
    jsonld: dict | None = None
    body: str = ""                  # fallback HTML inside #root


def page_url(base: str, path: str, query: dict, lang: str) -> str:
    params = {**query, **({"lang": "en"} if lang == "en" else {})}
    return base + path + (f"?{urlencode(params)}" if params else "")


def render(template: str, page: Page, lang: str, base: str) -> str:
    """index.html with this page's head tags and fallback content filled in."""
    e = html.escape
    url = page_url(base, page.path, page.query, lang)
    head = [
        f'<link rel="canonical" href="{e(url)}" />',
        *(f'<link rel="alternate" hreflang="{HTML_LANG[l]}" href="{e(page_url(base, page.path, page.query, l))}" />'
          for l in LANGS),
        f'<link rel="alternate" hreflang="x-default" href="{e(page_url(base, page.path, page.query, "zh"))}" />',
        f'<meta property="og:site_name" content="{SITE_NAME}" />',
        f'<meta property="og:type" content="{page.og_type}" />',
        f'<meta property="og:title" content="{e(page.title)}" />',
        f'<meta property="og:description" content="{e(page.description)}" />',
        f'<meta property="og:url" content="{e(url)}" />',
        f'<meta property="og:locale" content="{OG_LOCALE[lang]}" />',
        f'<meta property="og:locale:alternate" content="{OG_LOCALE["en" if lang == "zh" else "zh"]}" />',
        f'<meta name="twitter:card" content="{"summary_large_image" if page.image else "summary"}" />',
        f'<meta name="twitter:title" content="{e(page.title)}" />',
        f'<meta name="twitter:description" content="{e(page.description)}" />',
    ]
    if page.image:
        head += [f'<meta property="og:image" content="{e(base + page.image)}" />',
                 f'<meta name="twitter:image" content="{e(base + page.image)}" />']
    if not page.index:
        head.append('<meta name="robots" content="noindex" />')
    if page.jsonld:
        data = json.dumps({"@context": "https://schema.org", **page.jsonld}, ensure_ascii=False).replace("</", "<\\/")
        head.append(f'<script type="application/ld+json">{data}</script>')

    out = re.sub(r'<html lang="[^"]*"', f'<html lang="{HTML_LANG[lang]}"', template, count=1)
    out = re.sub(r"<title>.*?</title>", lambda _: f"<title>{e(page.title)}</title>", out, count=1, flags=re.S)
    out = re.sub(r'<meta name="description" content="[^"]*"\s*/?>',
                 lambda _: f'<meta name="description" content="{e(page.description)}" />', out, count=1)
    out = out.replace("</head>", "    " + "\n    ".join(head) + "\n  </head>", 1)
    return out.replace('<div id="root"></div>', f'<div id="root">{page.body}</div>', 1)


# --- page builders. Each takes the data the API already serves. ---

def _link(path: str, text: str, lang: str, query: dict | None = None) -> str:
    return f'<a href="{html.escape(page_url("", path, query or {}, lang))}">{html.escape(text)}</a>'


def _nav(lang: str) -> str:
    zh = lang == "zh"
    items = [("/", "首页" if zh else "Home"), ("/roles", "定位实验室" if zh else "Role Lab"),
             ("/players", "球员名册" if zh else "Player Roster"), ("/teams", "球队体系" if zh else "Team Systems"),
             ("/rankings", "排名" if zh else "Rankings")]
    other = _link("/", "English", "en") if zh else _link("/", "中文", "zh")
    return "<nav>" + " · ".join(_link(p, t, lang) for p, t in items) + f" · {other}</nav>"


def _player_list(players: list[dict], season: str, lang: str, limit: int) -> str:
    items = []
    for p in players[:limit]:
        style = role_name(p.get("off_style"), lang)
        extra = " · ".join(x for x in (team_name(p.get("team"), lang), style,
                                       f"OVR {p['ovr']}" if p.get("ovr") is not None else "") if x)
        items.append(f"<li>{_link(f'/players/{p['player_id']}', p['name'], lang)} {html.escape(extra)}</li>")
    return "<ul>" + "".join(items) + "</ul>"


def home(lang: str, season: str, players: list[dict]) -> Page:
    zh = lang == "zh"
    regular = [p for p in players if p.get("in_fit")]

    def best(key: str) -> list[dict]:
        return sorted((p for p in regular if p.get(key) is not None), key=lambda p: -p[key])[:6]

    sections = [("得分火力最猛的球员", "Top scorers", "pts_36"), ("赛季最佳球员", "Best players", "ovr"),
                ("赛季最佳进攻球员", "Best offensive players", "off"),
                ("赛季最佳防守球员", "Best defensive players", "def")]
    lists = "".join(f"<h2>{name_zh if zh else name_en} ({html.escape(season)})</h2>"
                    f"{_player_list(best(key), season, lang, 6)}" for name_zh, name_en, key in sections)
    body = (f"<header><h1>Hoopedia</h1>{_nav(lang)}</header><main><p>{html.escape(SITE_DESC[lang])}</p>"
            f"{lists}</main>")
    return Page(200, SITE_TITLE[lang], SITE_DESC[lang], "/", body=body,
                jsonld={"@type": "WebSite", "name": SITE_NAME, "inLanguage": HTML_LANG[lang],
                        "description": SITE_DESC[lang]})


def roles_lab(lang: str, season: str | None) -> Page:
    zh = lang == "zh"
    title = f"{'定位实验室：NBA 球员打法原型' if zh else 'Role Lab: NBA player archetypes'} · {SITE_NAME}"
    desc = ("7 种进攻原型、4 种防守原型：看每名 NBA 球员是哪几种打法的混合，以及最接近每种原型的球员。" if zh else
            "7 offensive and 4 defensive archetypes: see which mix of styles makes up each NBA player, "
            "and who comes closest to each archetype.")
    names = "".join(f"<li>{html.escape(role_name(a, lang))}</li>" for a in NAMES_EN)
    body = (f"<header><h1>{'定位实验室' if zh else 'Role Lab'}</h1>{_nav(lang)}</header>"
            f"<main><p>{html.escape(desc)}</p><ul>{names}</ul></main>")
    return Page(200, title, desc, "/roles", {"season": season} if season else {}, body=body)


def roster(lang: str, season: str, players: list[dict], explicit_season: bool) -> Page:
    zh = lang == "zh"
    query = {"season": season} if explicit_season else {}
    title = f"{'NBA 球员名册' if zh else 'NBA player roster'} {season} · {SITE_NAME}"
    desc = (f"{season} 赛季全部 NBA 球员：打法原型、2K 式能力值和每 36 分钟数据。" if zh else
            f"Every NBA player of {season}: archetypes, 2K-style ratings and per-36 stats.")
    body = (f"<header><h1>{html.escape(title.split(' · ')[0])}</h1>{_nav(lang)}</header>"
            f"<main><p>{html.escape(desc)}</p>{_player_list(players, season, lang, 200)}</main>")
    return Page(200, title, desc, "/players", query, body=body)


def teams(lang: str, season: str, explicit_season: bool, view: dict) -> Page:
    zh = lang == "zh"
    title = f"{'NBA 球队进攻体系' if zh else 'NBA team offensive systems'} {season} · {SITE_NAME}"
    desc = (f"{season} 赛季每支 NBA 球队的进攻体系、球队评分（综合、进攻、防守）和主力轮换。" if zh else
            f"Every NBA team's offensive system, team ratings (overall, offense, defense) and rotation for {season}.")
    style_names = {s["style_id"]: s["name"] for s in view["styles"]}
    items = []
    for t in view["teams"]:
        style = style_names.get(t["style_id"]) or ""
        if not zh:
            style = STYLE_EN.get(style, style)
        rating = f"{'评分' if zh else 'rating'} {t['ovr']}" if t.get("ovr") is not None else ""
        items.append(f"<li>{html.escape(team_name(t['team'], lang))} · {html.escape(style)} · {html.escape(rating)}</li>")
    body = (f"<header><h1>{html.escape(title.split(' · ')[0])}</h1>{_nav(lang)}</header>"
            f"<main><p>{html.escape(desc)}</p><ul>{''.join(items)}</ul></main>")
    return Page(200, title, desc, "/teams", {"season": season} if explicit_season else {}, body=body)


def team(lang: str, season: str, explicit_season: bool, view: dict) -> Page:
    zh = lang == "zh"
    abbr, prof = view["team"], view["profile"]
    name = team_name(abbr, lang)
    title = f"{name} {season} {'阵容、评分与赛程' if zh else 'roster, ratings and schedule'} · {SITE_NAME}"
    st = view.get("standing")
    record = f"{st['wins']}-{st['losses']}" if st else ""
    desc = (f"{name} {season} 赛季球队评分 {prof.get('ovr')}，{record}。球员阵容、球员评分、数据和赛程。" if zh else
            f"{name} {season}: team rating {prof.get('ovr')}, {record}. Roster, player ratings, stats and schedule.")
    players = "".join(f"<li>{_link(f'/players/{p['player_id']}', p['name'], lang, {'season': season})} · OVR {p['ovr']}</li>"
                      for p in view["roster"] if p.get("ovr") is not None)
    body = (f"<header><h1>{html.escape(title.split(' · ')[0])}</h1>{_nav(lang)}</header>"
            f"<main><p>{html.escape(desc)}</p><ul>{players}</ul></main>")
    return Page(200, title, desc, f"/teams/{abbr}", {"season": season} if explicit_season else {}, body=body)


def rankings(lang: str, season: str, explicit_season: bool, view: dict) -> Page:
    zh = lang == "zh"
    title = f"{'NBA 排名：东西部排名与球员评分' if zh else 'NBA rankings: standings and player ratings'} {season} · {SITE_NAME}"
    desc = (f"{season} 赛季 NBA 东部、西部球队排名和球员综合评分排名，每天更新。" if zh else
            f"NBA {season} Eastern and Western Conference standings and player rating rankings, updated daily.")
    def conf(name: str, rows: list[dict]) -> str:
        items = "".join(f"<li>{r['rank']}. {html.escape(team_name(r['team'], lang))} {r['wins']}-{r['losses']}</li>" for r in rows)
        return f"<h2>{name}</h2><ol>{items}</ol>"
    players = "".join(f"<li>{html.escape(p['name'])} · {html.escape(team_name(p['team'], lang))} · OVR {p['ovr']}</li>"
                      for p in view["players"][:50])
    body = (f"<header><h1>{html.escape(title.split(' · ')[0])}</h1>{_nav(lang)}</header>"
            f"<main><p>{html.escape(desc)}</p>{conf('东部' if zh else 'Eastern Conference', view['east'])}"
            f"{conf('西部' if zh else 'Western Conference', view['west'])}"
            f"<h2>{'球员排名' if zh else 'Player rankings'}</h2><ol>{players}</ol></main>")
    return Page(200, title, desc, "/rankings", {"season": season} if explicit_season else {}, body=body)


def player(lang: str, season: str, explicit_season: bool, p: dict) -> Page:
    zh = lang == "zh"
    name, team = p["name"], team_name(p.get("team"), lang)
    rating, career = p.get("rating") or {}, p.get("career_rating") or {}
    off, de = (p.get("roles") or {}).get("offense"), (p.get("roles") or {}).get("defense")
    ovr = rating.get("ovr")
    stats = p.get("stats") or {}

    def mix_text(side: dict | None) -> str:
        if not side:
            return ""
        return ("、" if zh else ", ").join(f"{role_name(m['name'], lang)} {round(m['weight'] * 100)}%"
                                          for m in side["mix"][:3] if m["weight"] >= 0.1)

    if zh:
        title = f"{name} 的打法原型与超能力 · NBA {season} · {SITE_NAME}"
        parts = [f"{name}（{team}）{season} 赛季"]
        if off:
            parts.append(f"进攻定位：{role_name(off['style'], lang)}")
        if de:
            parts.append(f"防守：{role_name(de['style'], lang)}")
        if ovr is not None:
            parts.append(f"能力值 {ovr}")
        if career.get("peak") is not None:
            parts.append(f"生涯巅峰 {round(career['peak'])}")
        powers = [pw["name"] for pw in p.get("powers") or []]
        if powers:
            parts.append("超能力：" + "、".join(powers))
        desc = "，".join(parts) + "。"
    else:
        title = f"{name}: archetypes and superpowers · NBA {season} · {SITE_NAME}"
        parts = [f"{name} ({team}), {season}"]
        if off:
            parts.append(f"offense: {role_name(off['style'], lang)}")
        if de:
            parts.append(f"defense: {role_name(de['style'], lang)}")
        if ovr is not None:
            parts.append(f"OVR {ovr}")
        if career.get("peak") is not None:
            parts.append(f"career peak {round(career['peak'])}")
        desc = ", ".join(parts) + "."

    def stat(code: str, label_zh: str, label_en: str, pct: bool = False) -> str:
        v = stats.get(code)
        if v is None:
            return ""
        text = f"{v * 100:.1f}%" if pct else f"{v:.1f}"
        return f"<li>{label_zh if zh else label_en}: {text}</li>"

    body = (
        f"<header>{_nav(lang)}</header><main><h1>{html.escape(name)}</h1>"
        f"<p>{html.escape(desc)}</p>"
        + (f"<h2>{'进攻原型' if zh else 'Offensive mix'}</h2><p>{html.escape(mix_text(off))}</p>" if off else "")
        + (f"<h2>{'防守原型' if zh else 'Defensive mix'}</h2><p>{html.escape(mix_text(de))}</p>" if de else "")
        + "<ul>" + stat("pts_36", "每 36 分钟得分", "Points per 36") + stat("reb_36", "每 36 分钟篮板", "Rebounds per 36")
        + stat("ast_36", "每 36 分钟助攻", "Assists per 36") + stat("ts_pct", "真实命中率", "True shooting", True)
        + "</ul>"
        + _similar(off, lang) + "</main>"
    )
    jsonld = {"@type": "Person", "name": name, "description": desc}
    if p.get("team") in TEAMS:
        jsonld["affiliation"] = {"@type": "SportsTeam", "name": TEAMS[p["team"]][1], "sport": "Basketball"}
    return Page(200, title, desc, f"/players/{p['player_id']}", {"season": season} if explicit_season else {},
                og_type="profile", jsonld=jsonld, body=body)


def _similar(side: dict | None, lang: str) -> str:
    if not side or not side.get("similar"):
        return ""
    links = " · ".join(_link(f"/players/{s['player_id']}", s["name"], lang) for s in side["similar"])
    return f"<h2>{'打法相近的球员' if lang == 'zh' else 'Similar players'}</h2><p>{links}</p>"


def coming_soon(lang: str, path: str, title_zh: str, title_en: str) -> Page:
    title = f"{title_zh if lang == 'zh' else title_en} · {SITE_NAME}"
    return Page(200, title, SITE_DESC[lang], path, index=False,
                body=f"<header><h1>{html.escape(title)}</h1>{_nav(lang)}</header>")


def not_found(lang: str, path: str) -> Page:
    title = f"{'走错片场了' if lang == 'zh' else 'Page not found'} · {SITE_NAME}"
    return Page(404, title, SITE_DESC[lang], path, index=False,
                body=f"<header><h1>{html.escape(title)}</h1>{_nav(lang)}</header>")


def robots(base: str) -> str:
    return f"User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {base}/sitemap.xml\n"


def sitemap(base: str, paths: list[tuple[str, dict]]) -> str:
    """Every indexable page in both languages, each listing its alternates."""
    e = html.escape
    urls = []
    for path, query in paths:
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{HTML_LANG[l]}" href="{e(page_url(base, path, query, l))}"/>'
                       for l in LANGS)
        alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{e(page_url(base, path, query, "zh"))}"/>'
        urls += [f"<url><loc>{e(page_url(base, path, query, l))}</loc>{alts}</url>" for l in LANGS]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(urls) + "\n</urlset>\n")
