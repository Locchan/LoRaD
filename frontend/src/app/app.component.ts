import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ApiService } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, FormsModule, CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  username = '';
  password = '';
  isLoading = false;
  error = '';

  constructor(private apiService: ApiService) {}

  onSubmit() {
    if (this.isLoading) return;
    
    this.isLoading = true;
    this.error = '';

    this.apiService.login(this.username, this.password).subscribe({
      next: () => {
        // Login successful
        this.isLoading = false;
        // You can add navigation logic here later
      },
      error: (error) => {
        this.isLoading = false;
        if (error.status === 401) {
          this.error = 'Invalid username or password';
        } else {
          this.error = 'An error occurred. Please try again.';
        }
      }
    });
  }
}
