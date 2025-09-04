import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { interval, Subscription, forkJoin, of } from 'rxjs';
import { catchError, switchMap, tap } from 'rxjs/operators';
import { 
  AvailablePlayersResponse, 
  RadioStationsResponse, 
  YandexStationsResponse,
  CurrentPlayerResponse,
  CurrentStationResponse
} from '../../interfaces/api.interfaces';

@Component({
  selector: 'app-player',
  templateUrl: './player.component.html',
  styleUrls: ['./player.component.scss'],
  standalone: true,
  imports: [FormsModule, CommonModule]
})
export class PlayerComponent implements OnInit, OnDestroy {
  currentUser: string | null = null;
  currentTrack = '';
  currentStation = '';
  
  // Player management
  availablePlayers: { [key: string]: string } = {};
  currentPlayer = '';
  selectedPlayer = '';
  
  // Station management
  availableStations: { [key: string]: string } = {};
  selectedStation = '';
  
  // Audio player
  audioPlayer: HTMLAudioElement | null = null;
  volume = 100;
  
  // Loading states
  isLoading = true;
  isPlayerLoading = false;
  
  private trackUpdateSubscription?: Subscription;

  constructor(
    private apiService: ApiService,
    private router: Router
  ) {}

  ngOnInit() {
    this.audioPlayer = new Audio('https://radio.locchan.dev/lorad/live');
    this.audioPlayer.volume = this.volume / 100;
    this.initializePlayer();
  }

  ngOnDestroy() {
    this.trackUpdateSubscription?.unsubscribe();
    this.audioPlayer?.pause();
  }

  private initializePlayer() {
    this.isLoading = true;
    
    // Get current user
    this.apiService.whoami().subscribe(response => {
      this.currentUser = response.username;
    });

    // Load all initial data sequentially
    this.loadAllDataSequentially();
  }

  private loadAllDataSequentially() {
    // Step 1: Get available players
    this.apiService.getAvailablePlayers().subscribe({
      next: (players) => {
        this.availablePlayers = players;
        console.log('Available players loaded:', players);
        
        // Step 2: Get current player
        this.apiService.getCurrentPlayer().subscribe({
          next: (currentPlayer) => {
            this.currentPlayer = currentPlayer.player;
            this.selectedPlayer = currentPlayer.player;
            console.log('Current player loaded:', currentPlayer.player);
            
            // Step 3: Load stations for current player
            this.loadStationsForCurrentPlayer();
          },
          error: (error) => {
            console.error('Failed to get current player:', error);
            // Set default player if none exists
            const defaultPlayer = Object.keys(this.availablePlayers)[0];
            if (defaultPlayer) {
              this.currentPlayer = defaultPlayer;
              this.selectedPlayer = defaultPlayer;
              this.loadStationsForCurrentPlayer();
            } else {
              this.isLoading = false;
            }
          }
        });
      },
      error: (error) => {
        console.error('Failed to load available players:', error);
        // Set default players
        this.availablePlayers = { player_radio: 'Radio Player', player_streaming: 'Streaming Player' };
        this.loadStationsForCurrentPlayer();
      }
    });
  }

  private loadStationsForCurrentPlayer() {
    // Determine which stations to load based on current player
    const stationsObservable = this.currentPlayer === 'player_radio' 
      ? this.apiService.getRadioStations() 
      : this.apiService.getYandexStations();

    stationsObservable.subscribe({
      next: (stations: { [key: string]: string }) => {
        this.availableStations = stations;
        console.log(`${this.currentPlayer} stations loaded:`, stations);
        this.loadCurrentStationAndPlay();
      },
      error: (error: any) => {
        console.error(`Failed to load ${this.currentPlayer} stations:`, error);
        this.loadCurrentStationAndPlay();
      }
    });
  }

  private loadCurrentStationAndPlay() {
    const currentStationObservable = this.currentPlayer === 'player_radio'
      ? this.apiService.getRadioCurrentStation()
      : this.apiService.getCurrentStation();

    currentStationObservable.subscribe({
      next: (response) => {
        this.currentStation = response.station;
        this.selectedStation = response.station;
        console.log(`Current station loaded: ${response.station} for ${this.currentPlayer}`);
        this.finalizeInitializationAndPlay();
      },
      error: (error: any) => {
        console.error(`Failed to get current station for ${this.currentPlayer}:`, error);
        this.finalizeInitializationAndPlay();
      }
    });
  }

  private finalizeInitializationAndPlay() {
    this.isLoading = false;
    this.isPlayerLoading = false; // Ensure player loading is also reset
    this.startTrackUpdates();
    
    // Automatically start playing music
    this.autoStartMusic();
  }

  private autoStartMusic() {
    if (this.audioPlayer && this.selectedStation) {
      // Small delay to ensure everything is loaded
      setTimeout(() => {
        console.log('Auto-starting music for station:', this.selectedStation);
        console.log('Audio player state:', this.audioPlayer);
        
        // Try to play music
        this.audioPlayer!.play().then(() => {
          console.log('Music started automatically');
        }).catch((error) => {
          console.error('Failed to auto-start music:', error);
          // Fallback: try to refresh stream and play again
          this.refreshStream();
          setTimeout(() => {
            this.audioPlayer!.play().catch(e => 
              console.error('Failed to auto-start music after refresh:', e)
            );
          }, 1000);
        });
      }, 1000); // Increased delay for better reliability
    } else {
      console.log('Cannot auto-start: audioPlayer or station not ready', {
        audioPlayer: !!this.audioPlayer,
        selectedStation: this.selectedStation
      });
    }
  }

  private startTrackUpdates() {
    this.trackUpdateSubscription = interval(2000).subscribe(() => {
      this.apiService.getWhatsPlaying().subscribe({
        next: (response: any) => {
          // Use 'playing' field as specified in requirements
          if (response && response.playing) {
            this.currentTrack = response.playing;
          } else {
            this.currentTrack = 'Нет информации о треке';
          }
        },
        error: (error: any) => {
          console.error('Failed to get current track:', error);
          this.currentTrack = 'Ошибка загрузки трека';
        }
      });
    });
  }

  onPlayerChange(player: string) {
    if (player && player !== this.currentPlayer) {
      this.switchToPlayer(player);
    }
  }

  private switchToPlayer(player: string) {
    this.isPlayerLoading = true;
    
    this.apiService.switchPlayer(player).subscribe({
      next: () => {
        this.currentPlayer = player;
        this.selectedPlayer = player;
        
        // Reload stations and current station for new player
        this.reloadStationsForPlayer(player);
      },
      error: (error) => {
        console.error('Failed to switch player:', error);
        this.isPlayerLoading = false;
      }
    });
  }

  private reloadStationsForPlayer(player: string) {
    const stationsObservable = player === 'player_radio' 
      ? this.apiService.getRadioStations() 
      : this.apiService.getYandexStations();

    stationsObservable.subscribe({
      next: (stations: { [key: string]: string }) => {
        this.availableStations = stations;
        console.log(`Stations reloaded for ${player}:`, stations);
        
        // After loading stations, get current station for this player
        this.loadCurrentStationAndPlay();
      },
      error: (error: any) => {
        console.error(`Failed to reload stations for ${player}:`, error);
        this.isPlayerLoading = false;
      }
    });
  }

  onStationChange(stationKey: string) {
    if (stationKey && stationKey !== this.currentStation) {
      // Get the value (API parameter) for the selected station key
      const stationValue = this.availableStations[stationKey];
      
      if (!stationValue) {
        console.error('Station value not found for key:', stationKey);
        return;
      }

      // Use appropriate switch method based on current player
      const switchObservable = this.currentPlayer === 'player_radio' 
        ? this.apiService.switchRadioStation(stationValue)
        : this.apiService.switchYandexStation(stationValue);

      switchObservable.subscribe({
        next: () => {
          this.currentStation = stationKey;
          this.selectedStation = stationKey;
          console.log(`Switched to station: ${stationKey} (value: ${stationValue}) on ${this.currentPlayer}`);
        },
        error: (error: any) => {
          console.error('Failed to switch station:', error);
        }
      });
    }
  }

  playPause() {
    if (!this.audioPlayer) return;

    if (this.audioPlayer.paused) {
      this.audioPlayer.play();
    } else {
      this.audioPlayer.pause();
    }
  }

  refreshStream() {
    if (this.audioPlayer) {
      this.audioPlayer.load();
      if (!this.audioPlayer.paused) {
        this.audioPlayer.play();
      }
    }
  }

  onVolumeChange(event: Event) {
    const target = event.target as HTMLInputElement;
    this.volume = parseInt(target.value);
    if (this.audioPlayer) {
      this.audioPlayer.volume = this.volume / 100;
    }
  }

  playRadio() {
    if (this.selectedStation) {
      this.onStationChange(this.selectedStation);
      if (this.audioPlayer) {
        this.audioPlayer.play();
      }
    }
  }

  onLogout() {
    this.apiService.logout();
    this.audioPlayer?.pause();
    this.trackUpdateSubscription?.unsubscribe();
    this.router.navigate(['/login']);
  }

  getPlayerDisplayName(playerKey: string): string {
    return this.availablePlayers[playerKey] || playerKey;
  }

  getStationDisplayName(stationKey: string): string {
    return stationKey; // Show the key (station name) directly
  }
}
