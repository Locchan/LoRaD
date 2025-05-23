import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  AuthRequest,
  AuthResponse,
  VersionResponse,
  WhoAmIResponse,
  UserResponse,
  YandexStationsResponse,
  WhatsPlayingResponse,
  CurrentStationResponse
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

  // Version endpoint
  getVersion(): Observable<VersionResponse> {
    return this.http.get<VersionResponse>(`${this.apiUrl}/version`);
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
  getAvailableStations(): Observable<YandexStationsResponse> {
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

  getCurrentTrack(): Observable<WhatsPlayingResponse> {
    return this.http.get<WhatsPlayingResponse>(
      `${this.apiUrl}/whatsplaying`,
      { headers: this.getAuthHeaders() }
    );
  }

  switchStation(newStation: string): Observable<UserResponse> {
    return this.http.post<UserResponse>(
      `${this.apiUrl}/yandex/switch_station`,
      { new_station: newStation },
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
}