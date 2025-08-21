import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlayerComponent } from './components/player/player.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, PlayerComponent],
  template: `
    <div class="app-container">
        <app-player></app-player>
    </div>
  `,
  styles: [
    `
    :host {
      display: block;
      min-height: 100vh;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
        Roboto, Helvetica, Arial, sans-serif;
    }
    `
  ],
})
export class AppComponent {
  constructor() {}
}
