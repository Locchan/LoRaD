import { Routes } from '@angular/router';
import { LoginComponent } from './components/login/login.component';
import { PlayerComponent } from './components/player/player.component';
import { ScheduleComponent } from './components/schedule/schedule.component';
import { authGuard } from './guards/auth.guard';
import { loginGuard } from './guards/login.guard';

export const routes: Routes = [
  { 
    path: 'login', 
    component: LoginComponent,
    // canActivate: [loginGuard]
  },
  { 
    path: '', 
    component: PlayerComponent,
    canActivate: [authGuard]
  },
  { 
    path: 'schedule', 
    component: ScheduleComponent,
    canActivate: [authGuard]
  },
  { 
    path: '**', 
    redirectTo: '' 
  }
];
