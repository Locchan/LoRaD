import { Component, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-logo',
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="logo-container">
      <img 
        src="logo.png" 
        alt="ФУТИК-НУТИК" 
        class="logo-image">
    </div>
  `,
  styles: [`
    .logo-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      padding: 8px;
    }

    .logo-image {
      max-width: 200px;
      max-height: 200px;
      object-fit: contain;
      border-radius: 4px;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
    }

    .powered-by {
      font-size: 10px;
      color: #666;
      text-align: center;
      font-weight: 500;
      opacity: 0.8;
    }

    @media (max-width: 768px) {
      .logo-container {
        padding: 6px;
      }
      
      .logo-image {
        max-width: 50px;
        max-height: 50px;
      }
      
      .powered-by {
        font-size: 9px;
      }
    }
  `]
})
export class LogoComponent {}
