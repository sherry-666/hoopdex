// Team names by stats.nba.com abbreviation: [Chinese name, English full name].
// Includes former abbreviations that appear in career tables.
export const TEAMS: Record<string, [string, string]> = {
  ATL: ["老鹰", "Atlanta Hawks"], BOS: ["凯尔特人", "Boston Celtics"], BKN: ["篮网", "Brooklyn Nets"],
  CHA: ["黄蜂", "Charlotte Hornets"], CHI: ["公牛", "Chicago Bulls"], CLE: ["骑士", "Cleveland Cavaliers"],
  DAL: ["独行侠", "Dallas Mavericks"], DEN: ["掘金", "Denver Nuggets"], DET: ["活塞", "Detroit Pistons"],
  GSW: ["勇士", "Golden State Warriors"], HOU: ["火箭", "Houston Rockets"], IND: ["步行者", "Indiana Pacers"],
  LAC: ["快船", "LA Clippers"], LAL: ["湖人", "Los Angeles Lakers"], MEM: ["灰熊", "Memphis Grizzlies"],
  MIA: ["热火", "Miami Heat"], MIL: ["雄鹿", "Milwaukee Bucks"], MIN: ["森林狼", "Minnesota Timberwolves"],
  NOP: ["鹈鹕", "New Orleans Pelicans"], NYK: ["尼克斯", "New York Knicks"], OKC: ["雷霆", "Oklahoma City Thunder"],
  ORL: ["魔术", "Orlando Magic"], PHI: ["76人", "Philadelphia 76ers"], PHX: ["太阳", "Phoenix Suns"],
  POR: ["开拓者", "Portland Trail Blazers"], SAC: ["国王", "Sacramento Kings"], SAS: ["马刺", "San Antonio Spurs"],
  TOR: ["猛龙", "Toronto Raptors"], UTA: ["爵士", "Utah Jazz"], WAS: ["奇才", "Washington Wizards"],
  // former
  NJN: ["新泽西篮网", "New Jersey Nets"], SEA: ["超音速", "Seattle SuperSonics"], VAN: ["温哥华灰熊", "Vancouver Grizzlies"],
  NOH: ["新奥尔良黄蜂", "New Orleans Hornets"], NOK: ["新奥尔良/俄城黄蜂", "New Orleans/Oklahoma City Hornets"],
  CHH: ["夏洛特黄蜂", "Charlotte Hornets"], CHA_BOBCATS: ["山猫", "Charlotte Bobcats"],
  TOT: ["合计", "Total"],
};

/** Display name for a team abbreviation (or "LAL/PHI" for a traded season). */
export function teamName(abbr: string | null | undefined, lang: "zh" | "en", long = false): string {
  if (!abbr) return "";
  return abbr.split("/").map((a) => {
    const t = TEAMS[a];
    if (!t) return a;
    return lang === "zh" ? t[0] : long ? t[1] : a;
  }).join(" / ");
}
