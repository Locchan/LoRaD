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
            
            // Step 3: Get available stations (both types)
            this.apiService.getAvailableStations().subscribe({
              next: (yandexStations) => {
                console.log('Yandex stations loaded:', yandexStations);
                
                this.apiService.getRadioStations().subscribe({
                  next: (radioStations) => {
                    console.log('Radio stations loaded:', radioStations);
                    
                    // Combine all stations
                    this.availableStations = { ...radioStations, ...yandexStations };
                    
                    // Step 4: Get current station based on player type
                    if (this.currentPlayer === 'player_radio') {
                      this.apiService.getRadioCurrentStation().subscribe({
                        next: (radioStation) => {
                          this.currentStation = radioStation.station;
                          this.selectedStation = radioStation.station;
                          console.log('Radio current station loaded:', radioStation.station);
                          this.finalizeInitializationAndPlay();
                        },
                        error: (error) => {
                          console.error('Failed to get radio current station:', error);
                          this.finalizeInitializationAndPlay();
                        }
                      });
                    } else {
                      this.apiService.getCurrentStation().subscribe({
                        next: (yandexStation) => {
                          this.currentStation = yandexStation.station;
                          this.selectedStation = yandexStation.station;
                          console.log('Yandex current station loaded:', yandexStation.station);
                          this.finalizeInitializationAndPlay();
                        },
                        error: (error) => {
                          console.error('Failed to get yandex current station:', error);
                          this.finalizeInitializationAndPlay();
                        }
                      });
                    }
                  },
                  error: (error) => {
                    console.error('Failed to load radio stations:', error);
                    this.availableStations = { ...yandexStations };
                    this.loadCurrentStationAndPlay();
                  }
                });
              },
              error: (error) => {
                console.error('Failed to load yandex stations:', error);
                this.apiService.getRadioStations().subscribe({
                  next: (radioStations) => {
                    this.availableStations = radioStations;
                    this.loadCurrentStationAndPlay();
                  },
                  error: (error) => {
                    console.error('Failed to load any stations:', error);
                    this.loadCurrentStationAndPlay();
                  }
                });
              }
            });
          },
          error: (error) => {
            console.error('Failed to get current player:', error);
            // Set default player if none exists
            const defaultPlayer = Object.keys(this.availablePlayers)[0];
            if (defaultPlayer) {
              this.currentPlayer = defaultPlayer;
              this.selectedPlayer = defaultPlayer;
              this.loadStationsAndPlay();
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
        this.loadStationsAndPlay();
      }
    });
  }

  private loadStationsAndPlay() {
    // Load stations for current player
    if (this.currentPlayer === 'player_radio') {
      this.apiService.getRadioStations().subscribe({
        next: (stations) => {
          this.availableStations = stations;
          this.loadCurrentStationAndPlay();
        },
        error: (error) => {
          console.error('Failed to load radio stations:', error);
          this.loadCurrentStationAndPlay();
        }
      });
    } else {
      this.apiService.getAvailableStations().subscribe({
        next: (stations) => {
          this.availableStations = stations;
          this.loadCurrentStationAndPlay();
        },
        error: (error) => {
          console.error('Failed to load yandex stations:', error);
          this.loadCurrentStationAndPlay();
        }
      });
    }
  }

  private loadCurrentStationAndPlay() {
    if (this.currentPlayer === 'player_radio') {
      this.apiService.getRadioCurrentStation().subscribe({
        next: (response) => {
          this.currentStation = response.station;
          this.selectedStation = response.station;
          this.finalizeInitializationAndPlay();
        },
        error: (error) => {
          console.error('Failed to get radio current station:', error);
          this.finalizeInitializationAndPlay();
        }
      });
    } else {
      this.apiService.getCurrentStation().subscribe({
        next: (response) => {
          this.currentStation = response.station;
          this.selectedStation = response.station;
          this.finalizeInitializationAndPlay();
        },
        error: (error) => {
          console.error('Failed to get yandex current station:', error);
          this.finalizeInitializationAndPlay();
        }
      });
    }
  }

  private finalizeInitializationAndPlay() {
    this.isLoading = false;
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
      this.apiService.getCurrentTrack().subscribe({
        next: (response) => {
          if (response && typeof response === 'object') {
            if ('track' in response && response.track && typeof response.track === 'string') {
              this.currentTrack = response.track;
            } else if ('player_readable' in response && response.player_readable && typeof response.player_readable === 'string') {
              this.currentTrack = response.player_readable;
            } else {
              this.currentTrack = 'Трек загружается...';
            }
          } else {
            this.currentTrack = 'Трек загружается...';
          }
        },
        error: (error) => {
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
        
        // Reload stations based on new player
        this.reloadStationsForPlayer(player);
        
        // Get current station for new player
        this.loadCurrentStationAndPlay();
      },
      error: (error) => {
        console.error('Failed to switch player:', error);
        this.isPlayerLoading = false;
      }
    });
  }

  private reloadStationsForPlayer(player: string) {
    if (player === 'player_radio') {
      this.apiService.getRadioStations().subscribe({
        next: (stations) => {
          this.availableStations = stations;
          this.isPlayerLoading = false;
        },
        error: (error) => {
          console.error('Failed to load radio stations:', error);
          this.isPlayerLoading = false;
        }
      });
    } else {
      this.apiService.getAvailableStations().subscribe({
        next: (stations) => {
          this.availableStations = stations;
          this.isPlayerLoading = false;
        },
        error: (error) => {
          console.error('Failed to load yandex stations:', error);
          this.isPlayerLoading = false;
        }
      });
    }
  }

  onStationChange(station: string) {
    if (station && station !== this.currentStation) {
      this.apiService.switchStation(station).subscribe({
        next: () => {
          this.currentStation = station;
          this.selectedStation = station;
        },
        error: (error) => {
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
    return this.availableStations[stationKey] || stationKey;
  }
}
