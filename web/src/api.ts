import { useQuery } from "@tanstack/react-query";

export type Side = "offense" | "defense";
export const SIDE_LABEL: Record<Side, string> = { offense: "进攻", defense: "防守" };

export interface RoleType {
  level: "family" | "archetype";
  type_id: number;
  name: string;
  n_fit: number;
  profile: Record<string, number>;
}
export interface Axis { method: "factor" | "lda"; axis: string; name: string; high: string; low: string }
export interface RolePlayer {
  player_id: number; name: string; team: string; minutes: number; in_fit: boolean;
  family_id: number; family_name: string; top_archetype_id: number; top_weight: number;
  style_label: string; weights: Record<string, number>;
  x: number; y: number; f1: number; f2: number; f3: number; l1: number; l2: number; l3: number;
}
export interface RoleView { families: RoleType[]; archetypes: RoleType[]; axes: Axis[]; players: RolePlayer[] }

export interface PlayerRow {
  player_id: number; name: string; team: string; gp: number; minutes: number; in_fit: boolean;
  pts_36: number | null; ts_pct: number | null; usg_pct: number | null;
  off_family: string | null; off_style: string | null; off_top: number | null;
  def_family: string | null; def_style: string | null; def_top: number | null;
  ovr: number | null; off: number | null; def: number | null;
}
export interface Power {
  side: Side; feature: string; name: string; description: string; grade: "S" | "A" | "B"; z: number; value: number | null;
}
export interface SideRole {
  family: string; style: string; top_weight: number; in_fit: boolean;
  mix: { id: number; name: string; weight: number }[];
  similar: { player_id: number; name: string; team: string; style_label: string; similarity: number }[];
  blend_weight: number | null; prior_season: string | null;
}
export interface PlayerDetail {
  player_id: number; name: string; team: string; gp: number; minutes: number; in_fit: boolean;
  stats: Record<string, number | null>; percentiles: Record<string, number>; compare_season: string;
  rating: SeasonRating | null; career_rating: CareerRating | null;
  roles: Partial<Record<Side, SideRole>>; powers: Power[];
  injury: Injury | null;
}
export interface Injury {
  status: "Out" | "Day-To-Day" | string; body_part: string | null; detail: string | null; side: string | null;
  return_date: string | null; short_comment: string | null; long_comment: string | null;
  reported_at: string | null; updated_at: string;
}
export interface RecentGame {
  game_id: string; game_date: string; team: string; opp: string; home: boolean; team_score: number | null; opp_score: number | null;
  started: boolean | null; dnp_reason: string | null; min: number | null; pts: number | null; reb: number | null; ast: number | null;
  stl: number | null; blk: number | null; tov: number | null; fgm: number | null; fga: number | null; fg3m: number | null;
  fg3a: number | null; ftm: number | null; fta: number | null; plus_minus: number | null;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export interface SeasonRating {
  ovr: number; off: number; def: number; z: number; qualified: boolean; baseline_season: string; minutes: number; gp: number; model_version: string;
  detail: { contribution: number; scoring: number; on_court: number; reliability: number;
    pie: number; ts: number; usg: number; net: number; league_ts: number;
    blend?: { weight: number; own_ovr: number; own_off: number; own_def: number; prior_ovr: number; prior_off: number; prior_def: number };
    blend_prior?: string;
    off: { scoring: number; playmaking: number; off_rebounding: number; on_court: number;
      ortg: number; league_ortg: number; ast_pct: number; tov_pct: number; oreb_pct: number };
    def: { steals: number; blocks: number; def_rebounding: number; on_court: number;
      drtg: number; league_drtg: number; stl_36: number; blk_36: number; dreb_pct: number } };
}
export interface CareerRating {
  peak: number; peak_from: string; peak_to: string; avg_ovr: number; career: number;
  off_career: number | null; off_peak: number | null; def_career: number | null; def_peak: number | null; seasons: number; qualified_seasons: number;
}
export interface SeasonInfo { season: string; players: number; qualified: number; has_views: boolean; has_teams: boolean; in_progress: boolean }
export interface CareerLine {
  season?: string; team?: string; age?: number | null;
  gp: number; gs: number | null; min: number | null; fgm: number; fga: number; fg3m: number; fg3a: number;
  ftm: number; fta: number; oreb: number | null; dreb: number | null; reb: number; ast: number; stl: number | null;
  blk: number | null; tov: number | null; pf: number; pts: number;
  ovr?: number | null; off?: number | null; def?: number | null; ovr_qualified?: boolean | null;
}
export interface Career {
  player: { name: string; first_season: string | null; last_season: string | null } | null;
  regular: CareerLine[]; playoffs: CareerLine[];
  career: Partial<Record<"regular" | "playoffs", CareerLine>>;
  rating: CareerRating | null;
}

export interface TeamStyle { style_id: number; name: string | null; description: string | null; centroid: Record<string, number> }
export interface TeamProfile {
  team: string; style_id: number; defense_tag: string; off_mix: Record<string, number>; def_mix: Record<string, number>;
  off_z: Record<string, number>; avg_ovr: number | null; rotation_minutes: number;
  ovr: number | null; off: number | null; def: number | null; ortg: number | null; drtg: number | null;
  system: Record<string, number> | null; blend_weight: number | null;
  core: { player_id: number; name: string; minutes: number; style: string | null; ovr: number | null; off?: number | null; def?: number | null }[];
}
export interface TeamView { styles: TeamStyle[]; teams: TeamProfile[]; archetypes: Record<Side, string[]> }
export const useTeams = (season: string | undefined) =>
  useQuery({ queryKey: ["teams", season], queryFn: () => get<TeamView>(`/api/teams/${season}`), enabled: !!season });

export const useSeasons = () => useQuery({ queryKey: ["seasons"], queryFn: () => get<SeasonInfo[]>("/api/seasons") });
export const usePlayerSeasons = (id: number) =>
  useQuery({ queryKey: ["player-seasons", id], queryFn: () => get<string[]>(`/api/player/${id}/seasons`) });
export const useCareer = (id: number) =>
  useQuery({ queryKey: ["career", id], queryFn: () => get<Career>(`/api/player/${id}/career`) });
export interface Standing {
  team: string; conf: "East" | "West"; rank: number; wins: number; losses: number; win_pct: number | null;
  games_behind: number | null; home: string | null; road: string | null; conf_record: string | null;
  last10: string | null; streak: string | null; pts_for: number | null; pts_against: number | null; clincher: string | null;
}
export interface RankedPlayer { player_id: number; name: string; team: string | null; gp: number; minutes: number; ovr: number; off: number | null; def: number | null; page: boolean }
export interface Leader { player_id: number; name: string; team: string | null; gp: number; value: number; page: boolean }
export interface Rankings {
  season: string; updated_at: string; team_games: number; leaders: Record<string, Leader[]>; east: Standing[]; west: Standing[]; players: RankedPlayer[]; players_early: boolean;
}
export const useRankingSeasons = () =>
  useQuery({ queryKey: ["ranking-seasons"], queryFn: () => get<string[]>("/api/rankings/seasons") });
export const useRankings = (season: string | undefined) =>
  useQuery({ queryKey: ["rankings", season], queryFn: () => get<Rankings>(`/api/rankings/${season}`), enabled: !!season });
export const useRecentGames = (id: number) =>
  useQuery({ queryKey: ["recent", id], queryFn: () => get<RecentGame[]>(`/api/player/${id}/recent`) });
export const useRoleView = (season: string | undefined, side: Side) =>
  useQuery({ queryKey: ["roles", season, side], queryFn: () => get<RoleView>(`/api/roles/${season}/${side}`), enabled: !!season });
export const usePlayers = (season: string | undefined) =>
  useQuery({ queryKey: ["players", season], queryFn: () => get<PlayerRow[]>(`/api/players/${season}`), enabled: !!season });
export const usePlayer = (season: string | undefined, id: number) =>
  useQuery({ queryKey: ["player", season, id], queryFn: () => get<PlayerDetail>(`/api/players/${season}/${id}`), enabled: !!season });

/** The default season for the role explorer: the newest complete one with explorer views. */
/** The default season for the role explorer: the newest one with views, even while in progress. */
export function useSeason(): string | undefined {
  return useSeasons().data?.find((s) => s.has_views)?.season;
}
export const CAREER = "career";

/** The default season for lists and player pages: the newest one, even while in progress.
 *  Early in a season its ratings and roles blend with last season (ballstats/blend.py). */
export function useDefaultSeason(): string | undefined {
  return useSeasons().data?.[0]?.season;
}

export const seriesColor = (i: number) => `var(--series-${(i % 7) + 1})`;
export const pct = (v: number | null | undefined, digits = 0) => (v == null ? "—" : `${(v * 100).toFixed(digits)}%`);
export const num = (v: number | null | undefined, digits = 1) => (v == null ? "—" : v.toFixed(digits));

export interface TeamGame {
  game_id: string; season_type: number; opp: string; home: boolean; tipoff: string; game_date: string;
  completed: boolean; team_score: number | null; opp_score: number | null;
}
export interface TeamRosterRow {
  player_id: number; name: string; gp: number; minutes: number; ts_pct: number | null;
  off_style: string | null; def_style: string | null; ovr: number | null; off: number | null; def: number | null;
  pts: number | null; reb: number | null; ast: number | null;
  injury: Pick<Injury, "status" | "body_part" | "detail" | "side" | "return_date" | "short_comment"> | null;
  departed: boolean;   // played for the team, then was traded away
  avail: number;   // how much he counts toward the team's rating: 0 = left out, 1 = fully
}
export interface TeamPageData {
  team: string; season: string; seasons: string[]; games: TeamGame[]; roster: TeamRosterRow[];
  standing: { conf: "East" | "West"; rank: number; wins: number; losses: number; win_pct: number | null; home: string | null; road: string | null;
    last10: string | null; streak: string | null; pts_for: number | null; pts_against: number | null } | null;
  profile: { style_id: number; style_name: string | null; defense_tag: string; ovr: number | null; off: number | null; def: number | null;
    ortg: number | null; drtg: number | null };
}
export const useTeamSeasons = (team: string) =>
  useQuery({ queryKey: ["team-seasons", team], queryFn: () => get<string[]>(`/api/team/${team}/seasons`) });
export const useTeamPage = (team: string, season: string | undefined) =>
  useQuery({ queryKey: ["team-page", team, season], queryFn: () => get<TeamPageData>(`/api/team/${team}/${season}`), enabled: !!season });

export interface MatchupCell { off_style: number; def_tag: string; raw_effect: number; effect: number; se: number; n: number; off_teams: number }
export interface MatchupView {
  cells: MatchupCell[]; styles: { style_id: number; name: string | null }[];
  meta: { model_version: string; seasons: string[]; n_games: number; p_value: number; season_corr: number | null; tau: number } | null;
}
export const useMatchups = () => useQuery({ queryKey: ["matchups"], queryFn: () => get<MatchupView>("/api/matchups") });
