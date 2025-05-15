import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
  standalone: true,
  imports: [FormsModule, CommonModule]
})
export class LoginComponent {
  username = '';
  password = '';
  isLoading = false;
  error = '';

  constructor(
    private apiService: ApiService,
    private router: Router
  ) {}

  onSubmit() {
    if (this.isLoading) return;
    
    this.isLoading = true;
    this.error = '';

    this.apiService.login(this.username, this.password).subscribe({
      next: () => {
        this.isLoading = false;
        this.router.navigate(['/']);
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
