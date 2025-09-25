import { Component, OnInit, signal, computed, ChangeDetectionStrategy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { BackgroundService } from '../../services/background.service';
import { ScheduleTime, NewsSchedule } from '../../interfaces/api.interfaces';

@Component({
  selector: 'app-schedule',
  imports: [CommonModule, FormsModule, RouterModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="schedule-container" [style.background-image]="'url(' + backgroundImage() + ')'">
      <header class="schedule-header">
        <div class="logo-section">
          <h1 class="app-title">
            <i class="fas fa-calendar-alt"></i>
            Расписание рекламы
          </h1>
          <p class="app-subtitle">Управление временем выпусков рекламы</p>
        </div>
        
        <nav class="navigation">
          <a routerLink="/" class="nav-link">
            <i class="fas fa-play-circle"></i>
            Плеер
          </a>
          <a routerLink="/schedule" class="nav-link active">
            <i class="fas fa-calendar-alt"></i>
            Реклама
          </a>
        </nav>
        
        <div class="user-info">
          <span class="username">{{ currentUser() }}</span>
          <button class="logout-button" (click)="onLogout()">
            <i class="fas fa-sign-out-alt"></i>
            Выйти
          </button>
        </div>
      </header>

      <div class="main-content">
        <!-- Schedule Management Section -->
        <div class="schedule-section">
          <div class="section-header">
            <h2><i class="fas fa-clock"></i> Время выпусков рекламы</h2>
            <p class="section-description">Настройте время, когда должна выходить реклама</p>
          </div>
          
          <div class="schedule-controls">
            <div class="add-time-control">
              <div class="time-input-group">
                <label for="newTime" class="time-label">Добавить время:</label>
                <input 
                  type="time" 
                  id="newTime"
                  [(ngModel)]="newTime"
                  class="time-input"
                  [disabled]="isLoading()">
                <button 
                  class="add-btn"
                  (click)="addTime()"
                  [disabled]="!newTime || isLoading()">
                  <i class="fas fa-plus"></i>
                  Добавить
                </button>
              </div>
            </div>

            <div class="times-list" *ngIf="scheduleTimes().length > 0">
              <div class="times-header">
                <h3>Настроенные времена</h3>
                <button 
                  class="save-btn"
                  (click)="saveSchedule()"
                  [disabled]="isLoading() || !hasChanges()">
                  <i class="fas fa-save"></i>
                  Сохранить изменения
                </button>
              </div>
              
              <div class="times-grid">
                <div 
                  *ngFor="let timeItem of scheduleTimes(); trackBy: trackByTime" 
                  class="time-item">
                  <div class="time-display">
                    <i class="fas fa-clock"></i>
                    <span class="time-text">{{ timeItem.time }}</span>
                  </div>
                  <div class="time-actions">
                    <button 
                      class="remove-btn"
                      (click)="removeTime(timeItem)"
                      [disabled]="isLoading()">
                      <i class="fas fa-trash"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div class="empty-state" *ngIf="scheduleTimes().length === 0 && !isLoading()">
              <div class="empty-icon">
                <i class="fas fa-calendar-times"></i>
              </div>
              <h3>Нет настроенных времен</h3>
              <p>Добавьте время для выпусков новостей, используя форму выше</p>
            </div>
          </div>
        </div>

        <!-- Loading State -->
        <div class="loading-section" *ngIf="isLoading()">
          <div class="loading-card">
            <i class="fas fa-spinner fa-spin"></i>
            <p>{{ loadingMessage() }}</p>
          </div>
        </div>

        <!-- Success Message -->
        <div class="success-message" *ngIf="successMessage()">
          <div class="success-card">
            <i class="fas fa-check-circle"></i>
            <p>{{ successMessage() }}</p>
            <button class="close-btn" (click)="clearSuccessMessage()">
              <i class="fas fa-times"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  styleUrls: ['./schedule.component.scss']
})
export class ScheduleComponent implements OnInit {
  private backgroundService = inject(BackgroundService);
  
  // Signals for reactive state management
  scheduleTimes = signal<ScheduleTime[]>([]);
  isLoading = signal(false);
  loadingMessage = signal('');
  successMessage = signal('');
  newTime = '';
  currentUser = signal('');
  backgroundImage = this.backgroundService.currentBackgroundImage;

  // Computed properties
  hasChanges = computed(() => {
    const originalTimes = this.originalTimes.map(t => t.time).sort();
    const currentTimes = this.scheduleTimes().map(t => t.time).sort();
    return JSON.stringify(originalTimes) !== JSON.stringify(currentTimes);
  });

  private originalTimes: ScheduleTime[] = [];
  private readonly CONFIG_KEY = 'ENABLED_PROGRAMS/NewsSmall/start_times';

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadCurrentUser();
    this.loadSchedule();
  }

  trackByTime(index: number, item: ScheduleTime): string {
    return item.time;
  }

  loadCurrentUser(): void {
    const username = localStorage.getItem('username');
    if (username) {
      this.currentUser.set(username);
    }
  }

  loadSchedule(): void {
    this.isLoading.set(true);
    this.loadingMessage.set('Загрузка расписания...');

    this.apiService.getConfig(this.CONFIG_KEY).subscribe({
      next: (response) => {
        const times = response[this.CONFIG_KEY] as string[] || [];
        const scheduleTimes: ScheduleTime[] = times.map(time => ({
          time: time,
          enabled: true
        }));
        
        this.scheduleTimes.set(scheduleTimes);
        this.originalTimes = [...scheduleTimes];
        this.isLoading.set(false);
      },
      error: (error) => {
        console.error('Error loading schedule:', error);
        this.isLoading.set(false);
        this.showError('Ошибка загрузки расписания');
      }
    });
  }

  addTime(): void {
    if (!this.newTime) return;

    const timeExists = this.scheduleTimes().some(item => item.time === this.newTime);
    if (timeExists) {
      this.showError('Время уже существует');
      return;
    }

    const newTimeItem: ScheduleTime = {
      time: this.newTime,
      enabled: true
    };

    this.scheduleTimes.update(times => [...times, newTimeItem].sort((a, b) => a.time.localeCompare(b.time)));
    this.newTime = '';
  }

  removeTime(timeItem: ScheduleTime): void {
    this.scheduleTimes.update(times => 
      times.filter(item => item.time !== timeItem.time)
    );
  }

  saveSchedule(): void {
    if (!this.hasChanges()) return;

    this.isLoading.set(true);
    this.loadingMessage.set('Сохранение расписания...');

    const times = this.scheduleTimes().map(item => item.time);

    this.apiService.setConfig(this.CONFIG_KEY, times).subscribe({
      next: (response) => {
        this.isLoading.set(false);
        this.originalTimes = [...this.scheduleTimes()];
        this.showSuccess('Расписание успешно сохранено');
      },
      error: (error) => {
        console.error('Error saving schedule:', error);
        this.isLoading.set(false);
        this.showError('Ошибка сохранения расписания');
      }
    });
  }

  onLogout(): void {
    this.apiService.logout();
    window.location.href = '/login';
  }

  private showSuccess(message: string): void {
    this.successMessage.set(message);
    setTimeout(() => this.clearSuccessMessage(), 3000);
  }

  private showError(message: string): void {
    // В реальном приложении здесь можно добавить toast уведомления
    console.error(message);
    alert(message);
  }

  clearSuccessMessage(): void {
    this.successMessage.set('');
  }
}
