import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from './services/api.service';
import {
  VersionResponse,
  YandexStationsResponse,
  CurrentStationResponse,
  UserResponse,
  CurrentTrackResponse,
} from './interfaces/api.interfaces';
import { Subscription, interval } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="app-container">
      <!-- Header -->
      <header class="header">
        <h1>LoRaD Radio Control</h1>
        <div class="auth-section" *ngIf="!isAuthenticated">
          <input
            [(ngModel)]="loginData.username"
            placeholder="Username"
            class="input-field"
          />
          <input
            [(ngModel)]="loginData.password"
            type="password"
            placeholder="Password"
            class="input-field"
          />
          <button (click)="login()" class="btn btn-primary">Login</button>
          <button (click)="register()" class="btn btn-secondary">
            Register
          </button>
        </div>
        <div class="user-info" *ngIf="isAuthenticated">
          <span>Welcome, {{ username }}</span>
          <button (click)="logout()" class="btn btn-danger">Logout</button>
        </div>
      </header>

      <!-- Main Content -->
      <main class="main-content" *ngIf="isAuthenticated">
        <!-- Station Selection -->
        <section class="station-section">
          <div class="station-controls">
            <div class="dropdown-group">
              <label>Type:</label>
              <select
                [(ngModel)]="selectedType"
                (change)="onTypeChange()"
                class="select-field"
              >
                <option value="">Select Type</option>
                <option value="radio">Radio</option>
                <option value="yandex">Yandex Music</option>
              </select>
            </div>

            <div class="dropdown-group">
              <label>Station:</label>
              <select
                [(ngModel)]="selectedStation"
                (change)="onStationChange()"
                class="select-field"
                [disabled]="!selectedType || isLoadingStations"
              >
                <option value="">
                  {{ isLoadingStations ? 'Loading...' : 'Select Station' }}
                </option>
                <option
                  *ngFor="let station of availableStations"
                  [value]="station.value"
                >
                  {{ station.label }}
                </option>
              </select>
              <div class="loading-indicator" *ngIf="isLoadingStations">
                <span>Loading stations...</span>
              </div>
            </div>
          </div>


        </section>

        <!-- Audio Player -->
        <section class="player-section">

          <!-- Track Info Display -->
          <div class="track-info" *ngIf="currentTrack">
            <div class="track-player">{{ currentTrack.player_readable }}</div>
            <div class="track-name">{{ currentTrack.playing }}</div>
            <div class="track-type">{{ currentTrack.player_tech }}</div>
          </div>

          <div class="player-controls">
            <button
              (click)="playPause()"
              class="btn btn-control"
              [class.btn-pause]="!isPlaying"
              [class.btn-play]="isPlaying"
            >
              {{ isPlaying ? '⏸️ Pause' : '▶️ Play' }}
            </button>

            <button
              (click)="refreshStream()"
              class="btn btn-refresh"
              title="Refresh track info"
            >
              🔄 Refresh
            </button>



            <div class="volume-control">
              <label>Volume:</label>
              <input
                type="range"
                [(ngModel)]="volume"
                (input)="onVolumeChange()"
                min="0"
                max="100"
                class="volume-slider"
              />
              <span class="volume-value">{{ volume }}%</span>
            </div>
          </div>
        </section>
      </main>

      <!-- Login Required Message -->
      <div class="login-required" *ngIf="!isAuthenticated">
        <p>Please log in to access the radio control panel.</p>
      </div>
    </div>
  `,
  styles: [
    `
    :host {
      display: block;
      min-height: 100vh;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
          Roboto, Helvetica, Arial, sans-serif, 'Apple Color Emoji',
          'Segoe UI Emoji', 'Segoe UI Symbol';
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

      .app-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
      }

      .header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 30px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 20px;
      }

      .header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
      }

      .auth-section,
      .user-info {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
      }

      .input-field {
        padding: 10px 15px;
        border: 1px solid #ddd;
        border-radius: 8px;
        font-size: 14px;
        min-width: 150px;
      }

      .btn {
        padding: 10px 20px;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .btn-primary {
        background: #007bff;
        color: white;
      }

      .btn-primary:hover {
        background: #0056b3;
        transform: translateY(-2px);
      }

      .btn-secondary {
        background: #6c757d;
        color: white;
      }

      .btn-secondary:hover {
        background: #545b62;
        transform: translateY(-2px);
      }

      .btn-danger {
        background: #dc3545;
        color: white;
      }

      .btn-danger:hover {
        background: #c82333;
        transform: translateY(-2px);
      }

      .btn-control {
        background: #28a745;
        color: white;
        font-size: 16px;
        padding: 15px 30px;
      }

      .btn-control:hover {
        background: #1e7e34;
        transform: translateY(-2px);
      }

      .btn-play {
        background: #28a745;
      }

      .btn-pause {
        background: #ffc107;
        color: #333;
      }

      .btn-refresh {
        background: #17a2b8;
        color: white;
        font-size: 14px;
        padding: 12px 20px;
      }

           .btn-refresh:hover {
       background: #138496;
       transform: translateY(-2px);
     }





      .main-content {
        display: grid;
        gap: 30px;
      }

      .station-section,
      .player-section,
      .info-section {
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e9ecef;
      }



      .station-controls {
        display: flex;
        gap: 30px;
        align-items: flex-end;
        flex-wrap: wrap;
        margin-bottom: 20px;
      }

      .dropdown-group {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .dropdown-group label {
        font-weight: 600;
        color: #555;
        font-size: 14px;
      }

      .select-field {
        padding: 12px 15px;
        border: 2px solid #ddd;
        border-radius: 8px;
        font-size: 14px;
        min-width: 200px;
        background: white;
        transition: border-color 0.2s ease;
      }

      .select-field:focus {
        border-color: #007bff;
        outline: none;
      }

      .select-field:disabled {
        background: #f8f9fa;
        color: #6c757d;
        cursor: not-allowed;
      }

      .select-field option {
        padding: 8px 12px;
        font-size: 14px;
      }

      .select-field option:first-child {
        font-style: italic;
        color: #6c757d;
      }



      .loading-indicator {
        margin-top: 5px;
        font-size: 12px;
        color: #007bff;
        font-style: italic;
      }



      .player-controls {
        display: flex;
        gap: 30px;
        align-items: center;
        flex-wrap: wrap;
        margin-bottom: 25px;
      }

      .volume-control {
        display: flex;
        align-items: center;
        gap: 15px;
      }

      .volume-control label {
        font-weight: 600;
        color: #555;
        min-width: 60px;
      }

      .volume-slider {
        width: 150px;
        height: 6px;
        border-radius: 3px;
        background: #ddd;
        outline: none;
        -webkit-appearance: none;
      }

      .volume-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #007bff;
        cursor: pointer;
      }

      .volume-slider::-moz-range-thumb {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #007bff;
        cursor: pointer;
        border: none;
      }

      .volume-value {
        font-weight: 600;
        color: #007bff;
        min-width: 50px;
      }

      .track-info {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #dee2e6;
        margin-bottom: 20px;
      }

      .track-player {
        font-size: 0.9rem;
        color: #6c757d;
        margin-bottom: 8px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .track-name {
        font-size: 1.2rem;
        font-weight: 600;
        color: #333;
        margin: 0 0 8px 0;
        line-height: 1.3;
      }

      .track-type {
        font-size: 0.8rem;
        color: #007bff;
        background: #e3f2fd;
        padding: 4px 8px;
        border-radius: 12px;
        display: inline-block;
        font-weight: 500;
      }

      .btn-sm {
        padding: 6px 12px;
        font-size: 12px;
        border-radius: 6px;
      }

      .btn-outline {
        background: transparent;
        border: 1px solid #007bff;
        color: #007bff;
      }

      .btn-outline:hover {
        background: #007bff;
        color: white;
      }

      .player-status {
        text-align: center;
        padding: 40px;
        color: #666;
        font-style: italic;
      }

      .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
      }

      .info-item {
        padding: 15px;
        background: #f8f9fa;
        border-radius: 8px;
        border-left: 4px solid #007bff;
      }

      .login-required {
        text-align: center;
        padding: 60px 20px;
        color: #666;
        font-size: 1.2rem;
      }

      @media (max-width: 768px) {
        .header {
          flex-direction: column;
          text-align: center;
        }

        .auth-section,
        .user-info {
          justify-content: center;
        }

        .station-controls,
        .player-controls {
          flex-direction: column;
          align-items: stretch;
        }

        .select-field,
        .input-field {
          min-width: auto;
          width: 100%;
        }

        .volume-control {
          flex-direction: column;
          align-items: stretch;
          gap: 10px;
        }

        .volume-slider {
          width: 100%;
        }
      }
    `,
  ],
})
export class AppComponent implements OnInit, OnDestroy {
  // Authentication
  isAuthenticated = false;
  username: string | null = null;
  loginData = { username: '', password: '' };

  // Station Selection
  selectedType = '';
  selectedStation = '';
  availableStations: { value: string; label: string }[] = [];
  currentStation: CurrentStationResponse | null =
    null;
  isLoadingStations = false;

  // Player
  isPlaying = false;
  volume = 50;
  currentTrack: { player_readable: string; player_tech: string; playing: string } | null = null;
  
  // Audio player for actual playback
  private audioElement: HTMLAudioElement | null = null;
  private streamUrl = 'https://radio.locchan.dev/lorad/live';

  private updateInterval: Subscription | null = null;

  constructor(private apiService: ApiService) {}

  ngOnInit() {
    try {
      this.checkAuth();
      if (this.isAuthenticated) {
        this.loadInitialData();
        this.startAutoUpdate();
        console.log('Component initialized successfully');
      }
    } catch (error) {
      console.error('Error in ngOnInit:', error);
    }
  }

  ngOnDestroy() {
    try {
      if (this.updateInterval) {
        this.updateInterval.unsubscribe();
      }
      if (this.audioElement) {
        try {
          this.audioElement.pause();
          this.audioElement.src = '';
        } catch (error) {
          console.error('Error cleaning up audio element in ngOnDestroy:', error);
        }
      }
      console.log('Component destroyed successfully');
    } catch (error) {
      console.error('Error in ngOnDestroy:', error);
    }
  }

  private checkAuth() {
    this.isAuthenticated = this.apiService.isAuthenticated();
    if (this.isAuthenticated) {
      this.username = localStorage.getItem('username');
      // Инициализируем аудио элемент если пользователь аутентифицирован
      try {
        this.initAudioElement();
        console.log('Auth check successful, audio element initialized');
      } catch (error) {
        console.error('Error initializing audio element in checkAuth:', error);
      }
    }
  }

  private loadInitialData() {
    // Загружаем текущий трек только если пользователь аутентифицирован
    if (this.isAuthenticated) {
      try {
        this.loadCurrentTrack();
        console.log('Initial data loaded successfully');
      } catch (error) {
        console.error('Error loading initial data:', error);
      }
    }
  }

  private initAudioElement() {
    if (!this.audioElement) {
      try {
        this.audioElement = new Audio();
        this.audioElement.volume = this.volume / 100;
        this.audioElement.preload = 'none';
        
        // Обработчики событий
        this.audioElement.addEventListener('play', () => {
          this.isPlaying = true;
          console.log('Audio started playing');
        });
        
        this.audioElement.addEventListener('pause', () => {
          this.isPlaying = false;
          console.log('Audio paused');
        });
        
        this.audioElement.addEventListener('error', (error) => {
          console.error('Audio error:', error);
          this.isPlaying = false;
        });
        
        this.audioElement.addEventListener('loadstart', () => {
          console.log('Audio loading started');
        });
        
        this.audioElement.addEventListener('canplay', () => {
          console.log('Audio can play');
        });
        
        this.audioElement.addEventListener('ended', () => {
          this.isPlaying = false;
          console.log('Audio ended');
        });
        
        console.log('Audio element initialized successfully');
      } catch (error) {
        console.error('Error initializing audio element:', error);
        this.audioElement = null;
      }
    } else {
      console.log('Audio element already exists');
    }
  }

  private startAutoUpdate() {
    // Update current track every 5 seconds
    this.updateInterval = interval(5000).subscribe({
      next: () => {
        if (this.isAuthenticated && this.isPlaying && this.audioElement) {
          try {
            this.loadCurrentTrack();
          } catch (error) {
            console.error('Error in auto update:', error);
          }
        }
      },
      error: (error) => {
        console.error('Error in auto update subscription:', error);
      }
    });
    console.log('Auto update started');
  }



  // Station Selection Methods
  onTypeChange() {
    try {
      this.selectedStation = '';
      this.availableStations = [];
      this.isLoadingStations = true;

      if (this.selectedType === 'radio') {
        // Для radio используем Yandex endpoints как fallback
        this.apiService.getAvailableStations().subscribe({
          next: (response: any) => {
            console.log('Raw radio response (using yandex):', response);

            // Проверяем структуру ответа и обрабатываем соответственно
            let stations: string[] = [];

            if (response.stations && Array.isArray(response.stations)) {
              // Стандартный формат
              stations = response.stations;
            } else if (response.playing) {
              // Альтернативный формат - используем текущую станцию
              stations = [response.playing];
            } else if (typeof response === 'object' && response !== null) {
              // Объект с ключами - извлекаем значения
              stations = Object.values(response);
              console.log('Extracted stations from object:', stations);
            } else {
              // Fallback - пустой массив
              stations = [];
              console.warn('Unexpected radio response format:', response);
            }

            // Маппим radio станции для отображения с иконками и форматированием
            this.availableStations = stations.map((station) => ({
              value: station,
              label: `📻 ${station}`,
            }));
            this.isLoadingStations = false;
            console.log('Radio stations loaded:', this.availableStations);
            console.log('isLoadingStations set to:', this.isLoadingStations);

            // Принудительная проверка через setTimeout
            setTimeout(() => {
              console.log(
                'Delayed check - isLoadingStations:',
                this.isLoadingStations
              );
            }, 100);
          },
          error: (error) => {
            this.isLoadingStations = false;
            console.error('Failed to load radio stations:', error);
            console.log('isLoadingStations set to:', this.isLoadingStations);
          },
        });
      } else if (this.selectedType === 'yandex') {
        this.apiService.getAvailableStations().subscribe({
          next: (response: any) => {
            console.log('Raw yandex response:', response);

            // Проверяем структуру ответа и обрабатываем соответственно
            let stations: string[] = [];

            if (response.stations && Array.isArray(response.stations)) {
              // Стандартный формат
              stations = response.stations;
            } else if (response.playing) {
              // Альтернативный формат - используем текущую станцию
              stations = [response.playing];
            } else if (typeof response === 'object' && response !== null) {
              // Объект с ключами - извлекаем значения
              stations = Object.values(response);
              console.log('Extracted stations from object:', stations);
            } else {
              // Fallback - пустой массив
              stations = [];
              console.warn('Unexpected yandex response format:', response);
            }

            // Маппим Yandex станции для отображения с иконками и форматированием
            this.availableStations = stations.map((station) => ({
              value: station,
              label: `🎵 ${station}`,
            }));
            this.isLoadingStations = false;
            console.log('Yandex stations loaded:', this.availableStations);
            console.log('isLoadingStations set to:', this.isLoadingStations);

            // Принудительная проверка через setTimeout
            setTimeout(() => {
              console.log(
                'Delayed check - isLoadingStations:',
                this.isLoadingStations
              );
            }, 100);
          },
          error: (error) => {
            this.isLoadingStations = false;
            console.error('Failed to load Yandex stations:', error);
            console.log('isLoadingStations set to:', this.isLoadingStations);
          },
        });
      }
    } catch (error) {
      console.error('Error in onTypeChange:', error);
      this.isLoadingStations = false;
    }
  }

  onStationChange() {
    if (this.selectedStation && this.selectedType) {
      try {
        this.switchStation();
        console.log('Station changed to:', this.selectedStation);
      } catch (error) {
        console.error('Error changing station:', error);
      }
    }
  }

  private switchStation() {
    try {
      if (this.selectedType === 'radio') {
        // Для radio используем Yandex endpoints как fallback
        this.apiService.switchStation(this.selectedStation).subscribe({
          next: () => {
            this.loadCurrentStation();
            // Обновляем трек после смены станции
            setTimeout(() => this.loadCurrentTrack(), 1000);

            // Обновляем информацию о треке для новой станции
            if (this.isPlaying) {
              setTimeout(() => this.loadCurrentTrack(), 1500);
            }
          },
          error: (error) => {
            console.error('Error switching radio station:', error);
          },
        });
      } else if (this.selectedType === 'yandex') {
        this.apiService.switchStation(this.selectedStation).subscribe({
          next: () => {
            this.loadCurrentStation();
            // Обновляем трек после смены станции
            setTimeout(() => this.loadCurrentTrack(), 1000);

            // Обновляем информацию о треке для новой станции
            if (this.isPlaying) {
              setTimeout(() => this.loadCurrentTrack(), 1500);
            }
          },
          error: (error) => {
            console.error('Error switching yandex station:', error);
          },
        });
      }
    } catch (error) {
      console.error('Error in switchStation:', error);
    }
  }

  private loadCurrentStation() {
    if (this.selectedType === 'radio') {
      // Для radio используем Yandex endpoints как fallback
      this.apiService.getCurrentStation().subscribe({
        next: (response: CurrentStationResponse) => {
          this.currentStation = response;
        },
        error: (error) => {
          console.error('Error loading radio current station:', error);
        },
      });
    } else if (this.selectedType === 'yandex') {
      this.apiService.getCurrentStation().subscribe({
        next: (response: CurrentStationResponse) => {
          this.currentStation = response;
        },
        error: (error) => {
          console.error('Error loading yandex current station:', error);
        },
      });
    }
  }

  // Player Methods - управление через API
  playPause() {
    try {
      if (this.isPlaying) {
        // Пауза - останавливаем радио через API
        this.pauseRadio();
      } else {
        // Воспроизведение - запускаем радио через API
        this.playRadio();
      }
    } catch (error) {
      console.error('Error in playPause:', error);
    }
  }

  // Запуск радио через API
  async playRadio() {
    console.log('Starting radio via API...');
    try {
      // Получаем доступные станции Yandex Music
      const stationsResponse = await this.apiService.getAvailableStations().toPromise();
      console.log('Available stations (raw):', stationsResponse);

      let stationList: string[] = [];
      if ((stationsResponse as any)?.stations && Array.isArray((stationsResponse as any).stations)) {
        stationList = (stationsResponse as any).stations as string[];
      } else if (Array.isArray(stationsResponse as any)) {
        stationList = stationsResponse as unknown as string[];
      } else if ((stationsResponse as any)?.playing) {
        stationList = [(stationsResponse as any).playing as string];
      } else if (stationsResponse && typeof stationsResponse === 'object') {
        stationList = Object.values(stationsResponse as unknown as Record<string, unknown>).filter(
          (v): v is string => typeof v === 'string'
        );
      }

      // Если есть станции, переключаемся на первую
      if (stationList.length > 0) {
        const firstStation = stationList[0];
        await this.apiService.switchStation(firstStation).toPromise();
        console.log('Switched to station:', firstStation);

        // Обновляем информацию о треке
        this.loadCurrentTrack();

        // Запускаем воспроизведение аудио потока
        if (this.audioElement) {
          this.audioElement.src = this.streamUrl;
          await this.audioElement.play();
          this.isPlaying = true;
          console.log('Audio playback started');
        } else {
          throw new Error('Audio element not initialized');
        }

        console.log('Radio started successfully');
      } else {
        console.log('No stations available');
        throw new Error('No stations available from API');
      }
    } catch (error: any) {
      console.error('Error starting radio:', error?.error ?? error);
      // Сбрасываем состояние воспроизведения при ошибке
      this.isPlaying = false;
    }
  }

  // Остановка радио через API
  async pauseRadio() {
    console.log('Stopping radio via API...');
    try {
      // Останавливаем воспроизведение аудио
      if (this.audioElement) {
        this.audioElement.pause();
        this.isPlaying = false;
        console.log('Audio paused');
      } else {
        console.warn('Cannot pause: no audio element');
      }
      console.log('Radio stopped');
    } catch (error) {
      console.error('Error stopping radio:', error);
    }
  }

  onVolumeChange() {
    // Обновляем громкость аудио элемента
    if (this.audioElement) {
      try {
        this.audioElement.volume = this.volume / 100;
        console.log('Volume changed to:', this.volume);
      } catch (error) {
        console.error('Error changing volume:', error);
      }
    } else {
      console.warn('Cannot change volume: no audio element');
    }
  }

  // Принудительное обновление стрима через API
  refreshStream() {
    if (this.isPlaying && this.audioElement) {
      console.log('Refreshing radio stream via API...');
      try {
        // Перезагружаем аудио поток
        this.audioElement.load();
        this.audioElement.play().catch(error => {
          console.error('Error restarting audio:', error);
          this.isPlaying = false;
        });
        // Перезагружаем информацию о треке
        this.loadCurrentTrack();
        console.log('Stream refreshed successfully');
      } catch (error) {
        console.error('Error refreshing stream:', error);
        this.isPlaying = false;
      }
    } else {
      console.log('Cannot refresh stream: not playing or no audio element');
    }
  }





  // Track Methods
  loadCurrentTrack() {
    this.apiService.getCurrentTrack().subscribe({
      next: (response: CurrentTrackResponse) => {
        // Преобразуем ответ в формат WhatsPlayingResponse для совместимости
        this.currentTrack = {
          player_readable: 'Yandex Music',
          player_tech: 'player_yandex',
          playing: response.track
        };
        console.log('Track updated:', this.currentTrack);
      },
      error: (error) => {
        console.error('Failed to load track:', error);
        // Сбрасываем трек при ошибке
        this.currentTrack = null;
      },
    });
  }

  // Authentication Methods
  login() {
    if (!this.loginData.username || !this.loginData.password) return;

    this.apiService
      .login(this.loginData.username, this.loginData.password)
      .subscribe({
        next: (response) => {
          this.isAuthenticated = true;
          this.username = this.loginData.username;
          this.loadInitialData();
          this.startAutoUpdate();
          this.loginData = { username: '', password: '' };
          console.log('Login successful');
        },
        error: (error) => {
          console.error('Login failed:', error);
          alert('Login failed. Please check your credentials.');
        },
      });
  }

  logout() {
    try {
      this.apiService.logout();
      this.isAuthenticated = false;
      this.username = null;
      
      // Останавливаем воспроизведение и очищаем аудио элемент
      if (this.audioElement) {
        try {
          this.audioElement.pause();
          this.audioElement.src = '';
          this.isPlaying = false;
        } catch (error) {
          console.error('Error cleaning up audio element:', error);
        }
      }
      
      this.resetData();
      if (this.updateInterval) {
        this.updateInterval.unsubscribe();
      }
      console.log('Logout successful');
    } catch (error) {
      console.error('Error in logout:', error);
    }
  }

  register() {
    if (!this.loginData.username || !this.loginData.password) return;

    this.apiService
      .registerUser(this.loginData.username, this.loginData.password)
      .subscribe({
        next: (response: UserResponse) => {
          alert('User registered successfully! Please login.');
          this.loginData = { username: '', password: '' };
          console.log('Registration successful');
        },
        error: (error) => {
          console.error('Registration failed:', error);
          alert('Registration failed. You may need admin privileges.');
        },
      });
  }



  private resetData() {
    try {
      this.selectedType = '';
      this.selectedStation = '';
      this.availableStations = [];
      this.currentStation = null;
      this.isLoadingStations = false;
      this.isPlaying = false;
      this.volume = 50;
      this.currentTrack = null;
      
      // Очищаем аудио элемент
      if (this.audioElement) {
        try {
          this.audioElement.pause();
          this.audioElement.src = '';
        } catch (error) {
          console.error('Error cleaning up audio element in resetData:', error);
        }
      }
      console.log('Data reset successfully');
    } catch (error) {
      console.error('Error in resetData:', error);
    }
  }
}
