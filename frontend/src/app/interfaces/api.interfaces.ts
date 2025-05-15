export interface VersionResponse {
  version: string;
}

export interface AuthRequest {
  username: string;
  password: string;
}

export interface AuthResponse {
  token: string;
}

export interface WhoAmIResponse {
  whoami: string;
}

export interface UserResponse {
  success: boolean;
  error?: string;
}

export interface YandexStationsResponse {
  [key: string]: string; // station name -> station id
}

export interface CurrentTrackResponse {
  track: string;
}

export interface CurrentStationResponse {
  station: string;
}

export interface ErrorResponse {
  error: string;
}