import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  AuthResponse,
  WhoAmIResponse,
  UserResponse,
  YandexStationsResponse,
  CurrentTrackResponse,
  CurrentStationResponse,
  AvailablePlayersResponse,
  RadioStationsResponse,
  CurrentPlayerResponse,
  WhatsPlayingResponse,
  ConfigGetRequest,
  ConfigSetRequest,
  ConfigResponse,
} from '../interfaces/api.interfaces';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiUrl = environment.apiUrl;
  private authToken: string | null = null;
  private username: string | null = null;

  constructor(private http: HttpClient) {
    // Try to restore auth from localStorage
    this.authToken = localStorage.getItem('authToken');
    this.username = localStorage.getItem('username');
  }

  private getAuthHeaders(): HttpHeaders {
    if (!this.authToken || !this.username) {
      throw new Error('Not authenticated');
    }
    return new HttpHeaders().set('Authorization', `${this.username}, ${this.authToken}`);
  }



  // User management endpoints
  login(username: string, password: string): Observable<AuthResponse> {
    return new Observable(subscriber => {
      this.http.post<AuthResponse>(`${this.apiUrl}/user/auth`, { username, password })
        .subscribe({
          next: (response) => {
            this.authToken = response.token;
            this.username = username;
            localStorage.setItem('authToken', response.token);
            localStorage.setItem('username', username);
            subscriber.next(response);
            subscriber.complete();
          },
          error: (error) => subscriber.error(error)
        });
    });
  }

  whoami(): Observable<WhoAmIResponse> {
    return this.http.get<WhoAmIResponse>(
      `${this.apiUrl}/user/whoami`,
      { headers: this.getAuthHeaders() }
    );
  }

  registerUser(username: string, password: string): Observable<UserResponse> {
    return this.http.post<UserResponse>(
      `${this.apiUrl}/user/register`,
      { username, password },
      { headers: this.getAuthHeaders() }
    );
  }

  removeUser(username: string): Observable<UserResponse> {
    return this.http.post<UserResponse>(
      `${this.apiUrl}/user/remove`,
      { username },
      { headers: this.getAuthHeaders() }
    );
  }

  // Yandex Music endpoints
  getYandexStations(): Observable<YandexStationsResponse> {
    return this.http.get<YandexStationsResponse>(
      `${this.apiUrl}/yandex/available_stations`,
      { headers: this.getAuthHeaders() }
    );
  }

  getCurrentStation(): Observable<CurrentStationResponse> {
    return this.http.get<CurrentStationResponse>(
      `${this.apiUrl}/yandex/current_station`,
      { headers: this.getAuthHeaders() }
    );
  }

  getWhatsPlaying(): Observable<WhatsPlayingResponse> {
    return this.http.get<WhatsPlayingResponse>(
      `${this.apiUrl}/whatsplaying`,
      { headers: this.getAuthHeaders() }
    );
  }

  switchYandexStation(newStation: string): Observable<UserResponse> {
    return this.http.post<UserResponse>(
      `${this.apiUrl}/yandex/switch_station`,
      { new_station: newStation },
      { headers: this.getAuthHeaders() }
    );
  }

  switchRadioStation(newStation: string): Observable<UserResponse> {
    return this.http.post<UserResponse>(
      `${this.apiUrl}/radio/switch_station`,
      { new_station: newStation },
      { headers: this.getAuthHeaders() }
    );
  }

  // Player management endpoints
  getAvailablePlayers(): Observable<AvailablePlayersResponse> {
    return this.http.get<AvailablePlayersResponse>(
      `${this.apiUrl}/available_players`,
      { headers: this.getAuthHeaders() }
    );
  }

  getRadioStations(): Observable<RadioStationsResponse> {
    return this.http.get<RadioStationsResponse>(
      `${this.apiUrl}/radio/available_stations`,
      { headers: this.getAuthHeaders() }
    );
  }

  getCurrentPlayer(): Observable<CurrentPlayerResponse> {
    return this.http.get<CurrentPlayerResponse>(
      `${this.apiUrl}/current_player`,
      { headers: this.getAuthHeaders() }
    );
  }

  switchPlayer(newPlayer: string): Observable<UserResponse> {
    return this.http.post<UserResponse>(
      `${this.apiUrl}/switch_player`,
      { new_player: newPlayer },
      { headers: this.getAuthHeaders() }
    );
  }

  getRadioCurrentStation(): Observable<CurrentStationResponse> {
    return this.http.get<CurrentStationResponse>(
      `${this.apiUrl}/radio/current_station`,
      { headers: this.getAuthHeaders() }
    );
  }

  logout(): void {
    this.authToken = null;
    this.username = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
  }

  isAuthenticated(): boolean {
    return this.authToken !== null && this.username !== null;
  }

  // Configuration management endpoints
  getConfig(key: string): Observable<ConfigResponse> {
    return this.http.post<ConfigResponse>(
      `${this.apiUrl}/admin/get_config`,
      { key },
      { headers: this.getAuthHeaders() }
    );
  }

  setConfig(key: string, value: string[] | string): Observable<UserResponse> {
    return this.http.post<UserResponse>(
      `${this.apiUrl}/admin/set_config`,
      { key, value },
      { headers: this.getAuthHeaders() }
    );
  }
}