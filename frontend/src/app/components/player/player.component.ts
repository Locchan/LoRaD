import { Component, OnDestroy, OnInit, inject, ViewChild, ElementRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { StorageService } from '../../services/storage.service';
import { BackgroundService } from '../../services/background.service';
import { interval, Subscription, forkJoin, of } from 'rxjs';
import { catchError, switchMap, tap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
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
  imports: [FormsModule, CommonModule, RouterModule]
})
export class PlayerComponent implements OnInit, OnDestroy {
  private backgroundService = inject(BackgroundService);
  private radioUrl = environment.radioUrl;
  currentUser: string | null = null;
  currentTrack = '';
  currentStation = '';
  
  // Radio title from environment
  radioTitle = environment.radioTitle;
  
  // Background image from service
  backgroundImage = this.backgroundService.currentBackgroundImage;
  
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
  
  // Panorama popup state
  showPanoramaPopup = true;
  videoPlaying = false;
  
  @ViewChild('newsVideo', { static: false }) newsVideoRef?: ElementRef<HTMLVideoElement>;
  
  private trackUpdateSubscription?: Subscription;

  constructor(
    private apiService: ApiService,
    private storageService: StorageService,
    public router: Router
  ) {}

  ngOnInit() {
    // Load volume from localStorage
    this.volume = this.storageService.loadVolume();
    
    this.audioPlayer = new Audio(this.radioUrl);
    this.audioPlayer.volume = this.volume / 100;
    this.initializePlayer();
    
    // Setup video autoplay workaround
    this.setupVideoAutoplayWorkaround();
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
    // Check if autoplay is enabled via environment variable
    if (!environment.autoplay) {
      console.log('Autoplay is disabled via AUTOPLAY environment variable');
      return;
    }

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
          if (response) {
            // Update track info
            this.currentTrack = response.playing || 'Нет информации о треке';
            
            // Check for Panorama popup
            // this.showPanoramaPopup = response.playing && response.playing.startsWith('Panorama');
            this.showPanoramaPopup = true;
            
            // Force video to play when popup appears
            setTimeout(() => this.forceVideoPlay(), 100);
            
            // Update current player if it differs from what we have
            if (response.player_tech && response.player_tech !== this.currentPlayer) {
              this.currentPlayer = response.player_tech;
              this.selectedPlayer = response.player_tech;
            }
            
            // Update current station if it differs from what we have
            if (response.station_tech && response.station_tech !== this.currentStation) {
              this.currentStation = response.station_tech;
              this.selectedStation = response.station_tech;
            }

            // Compare and update dropdowns with readable values
            this.updateDropdownsFromReadableValues(response);
          } else {
            this.currentTrack = 'Нет информации о треке';
            this.showPanoramaPopup = false;
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
    // Save volume to localStorage
    this.storageService.saveVolume(this.volume);
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

  private updateDropdownsFromReadableValues(response: any) {
    // Check if player_readable differs from current selection
    if (response.player_readable) {
      const currentPlayerDisplayName = this.getPlayerDisplayName(this.selectedPlayer);
      if (response.player_readable !== currentPlayerDisplayName) {
        // Find the player key that matches the readable name
        const matchingPlayerKey = Object.keys(this.availablePlayers).find(
          key => this.availablePlayers[key] === response.player_readable
        );
        
        if (matchingPlayerKey && matchingPlayerKey !== this.selectedPlayer) {
          console.log(`Updating player dropdown: ${this.selectedPlayer} -> ${matchingPlayerKey} (${response.player_readable})`);
          this.selectedPlayer = matchingPlayerKey;
          this.currentPlayer = matchingPlayerKey;
        }
      }
    }

    // Check if station_readable differs from current selection
    if (response.station_readable) {
      const currentStationDisplayName = this.getStationDisplayName(this.selectedStation);
      if (response.station_readable !== currentStationDisplayName) {
        // Find the station key that matches the readable name
        const matchingStationKey = Object.keys(this.availableStations).find(
          key => this.getStationDisplayName(key) === response.station_readable
        );
        
        if (matchingStationKey && matchingStationKey !== this.selectedStation) {
          console.log(`Updating station dropdown: ${this.selectedStation} -> ${matchingStationKey} (${response.station_readable})`);
          this.selectedStation = matchingStationKey;
          this.currentStation = matchingStationKey;
        }
      }
    }
  }

  setupVideoAutoplayWorkaround() {
    // Method 1: Simulate user interaction on page load
    document.addEventListener('DOMContentLoaded', () => {
      // Create a silent audio context to unlock autoplay
      this.createSilentAudioContext();
    });

    // Method 2: Try to play audio first to unlock video autoplay
    if (this.audioPlayer) {
      this.audioPlayer.play().then(() => {
        console.log('Audio played successfully, video autoplay should work now');
      }).catch(() => {
        console.log('Audio autoplay failed, trying video anyway');
      });
    }

    // Method 3: Add event listeners for user interaction
    document.addEventListener('click', () => this.unlockVideoAutoplay(), { once: true });
    document.addEventListener('keydown', () => this.unlockVideoAutoplay(), { once: true });
    document.addEventListener('touchstart', () => this.unlockVideoAutoplay(), { once: true });
  }

  createSilentAudioContext() {
    try {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      gainNode.gain.setValueAtTime(0, audioContext.currentTime);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.1);
      
      console.log('Silent audio context created to unlock autoplay');
    } catch (error) {
      console.log('Could not create audio context:', error);
    }
  }

  unlockVideoAutoplay() {
    console.log('User interaction detected, unlocking video autoplay');
    // This will be called when user interacts with the page
  }

  onVideoLoaded(event: Event) {
    const video = event.target as HTMLVideoElement;
    console.log('Video loaded, attempting to play...');
    
    // Try multiple approaches to play video
    this.attemptVideoPlay(video);
  }

  onVideoError(event: Event) {
    console.error('Video failed to load:', event);
  }

  attemptVideoPlay(video: HTMLVideoElement) {
    // Method 1: Direct play
    video.play().then(() => {
      console.log('Video started playing successfully');
      this.videoPlaying = true;
    }).catch((error) => {
      console.log('Direct play failed, trying workarounds:', error);
      
      // Method 2: Set currentTime and try again
      video.currentTime = 0;
      video.play().then(() => {
        console.log('Video started after currentTime reset');
        this.videoPlaying = true;
      }).catch((error2) => {
        console.log('CurrentTime reset failed, trying load + play:', error2);
        
        // Method 3: Load and play
        video.load();
        setTimeout(() => {
          video.play().then(() => {
            console.log('Video started after load');
            this.videoPlaying = true;
          }).catch((error3) => {
            console.log('All video play attempts failed:', error3);
          });
        }, 100);
      });
    });
  }

  forceVideoPlay() {
    if (this.newsVideoRef?.nativeElement) {
      const video = this.newsVideoRef.nativeElement;
      console.log('Forcing video to play...');
      this.attemptVideoPlay(video);
    }
  }
}
