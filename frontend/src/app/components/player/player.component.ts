import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { interval, Subscription } from 'rxjs';

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
  availableStations: { [key: string]: string } = {};
  selectedStation = '';
  audioPlayer: HTMLAudioElement | null = null;
  private trackUpdateSubscription?: Subscription;

  constructor(
    private apiService: ApiService,
    private router: Router
  ) {}

  ngOnInit() {
    // Create audio player
    this.audioPlayer = new Audio('https://radio.locchan.dev/lorad/live');
    this.initializePlayer();
  }

  ngOnDestroy() {
    this.trackUpdateSubscription?.unsubscribe();
    this.audioPlayer?.pause();
  }

  private initializePlayer() {
    // Get current user
    this.apiService.whoami().subscribe(response => {
      this.currentUser = response.whoami;
    });

    // Get available stations
    this.apiService.getAvailableStations().subscribe(stations => {
      this.availableStations = stations;
    });

    // Get current station
    this.apiService.getCurrentStation().subscribe(response => {
      this.currentStation = response.station;
      this.selectedStation = response.station;
    });

    // Start periodic track updates
    this.trackUpdateSubscription = interval(2000).subscribe(() => {
      this.apiService.getCurrentTrack().subscribe(response => {
        this.currentTrack = response.track;
      });
    });
  }

  onStationChange(station: string) {
    this.apiService.switchStation(station).subscribe({
      next: () => {
        this.currentStation = station;
      },
      error: (error) => {
        console.error('Failed to switch station:', error);
      }
    });
  }

  playPause() {
    if (!this.audioPlayer) return;

    if (this.audioPlayer.paused) {
      this.audioPlayer.play();
    } else {
      this.audioPlayer.pause();
    }
  }

  onLogout() {
    this.apiService.logout();
    this.audioPlayer?.pause();
    this.trackUpdateSubscription?.unsubscribe();
    this.router.navigate(['/login']);
  }
}
