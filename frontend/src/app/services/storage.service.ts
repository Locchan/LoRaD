import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class StorageService {
  private readonly VOLUME_KEY = 'lorad_volume';

  saveVolume(volume: number): void {
    localStorage.setItem(this.VOLUME_KEY, volume.toString());
  }

  loadVolume(): number {
    const savedVolume = localStorage.getItem(this.VOLUME_KEY);
    return savedVolume ? parseInt(savedVolume, 10) : 100;
  }

  clearVolume(): void {
    localStorage.removeItem(this.VOLUME_KEY);
  }
}
