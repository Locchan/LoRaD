import { inject } from '@angular/core';
import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401) {
        // Clear any stored auth data
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        
        // Redirect to login page
        router.navigate(['/login']);
      }
      
      return throwError(() => error);
    })
  );
};
