export interface AuthRequest {
  username: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  message?: string;
}

export interface VersionResponse {
  version: string;
}

export interface WhoAmIResponse {
  username: string;
}

export interface UserResponse {
  message: string;
  success: boolean;
}

export interface YandexStationsResponse {
  [key: string]: string;
}

export interface CurrentTrackResponse {
  track: string;
  artist?: string;
  album?: string;
}

export interface CurrentStationResponse {
  station: string;
}

export interface WhatsPlayingResponse {
  player_readable: string;
  player_tech: string;
  playing: string;
}

export interface CurrentPlayerResponse {
  player: string;
}

export interface AvailablePlayersResponse {
  [key: string]: string;
}

export interface RadioStationsResponse {
  [key: string]: string;
}

export interface SwitchPlayerRequest {
  new_player: string;
}

// Configuration interfaces
export interface ConfigGetRequest {
  key: string;
}

export interface ConfigSetRequest {
  key: string;
  value: string[] | string;
}

export interface ConfigResponse {
  [key: string]: string[] | string;
}

// Schedule interfaces
export interface ScheduleTime {
  time: string;
  enabled: boolean;
}

export interface NewsSchedule {
  times: ScheduleTime[];
}

