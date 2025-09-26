import { Injectable, signal, computed } from '@angular/core';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class BackgroundService {
  private readonly backgroundImages = [
    '1VuZTnscmraqYUZHZ1EQbecdrVfPm_l244Nl7PF1FkChpTa4adEpJMsKskpKRJXqryRvomDp.jpeg',
    '20160308_preview.jpeg',
    '3nKXMUBrk6P9d1hoN_4inCDZvSVkFQ_vkrA3YyqWggi6_F2aDFU7gJYF9CjD7v3MybVD8eGQ.jpeg',
    'IMG_1556_preview.jpeg',
    'IMG_5239_preview.jpeg',
    'IMG_6271_preview.jpeg',
    'ldTUiHwSCDrpbn_6FoA8x0jWqOayj8i54Vtw_WoLHPiBQ3eBBD4I3MiiVRiQ9LAl4CsJfS80.jpeg',
    'NKhd8U97D677IGE_3yYeNKT7Ii7nOjrV_8mItpXRK8HgfJmiYHb9A4OsbSQCCvapT6x16z4W.jpeg'
  ];

  private currentImageIndex = signal(0);

  // Computed signal that returns the current background image URL
  currentBackgroundImage = computed(() => {
    const imageName = this.backgroundImages[this.currentImageIndex()];
    const baseUrl = environment.production 
      ? 'https://radio.locchan.dev/ui' 
      : '';
    const imagePath = `https://radio.locchan.dev/ui/randomBackground/${imageName}`;
    console.log('Selected background image:', imagePath);
    return imagePath;
  });

  constructor() {
    // Set random background on service initialization
    this.setRandomBackground();
  }

  /**
   * Sets a random background image
   */
  setRandomBackground(): void {
    const randomIndex = Math.floor(Math.random() * this.backgroundImages.length);
    this.currentImageIndex.set(randomIndex);
  }

  /**
   * Gets the next background image in sequence
   */
  setNextBackground(): void {
    const nextIndex = (this.currentImageIndex() + 1) % this.backgroundImages.length;
    this.currentImageIndex.set(nextIndex);
  }

  /**
   * Gets the previous background image in sequence
   */
  setPreviousBackground(): void {
    const prevIndex = this.currentImageIndex() === 0 
      ? this.backgroundImages.length - 1 
      : this.currentImageIndex() - 1;
    this.currentImageIndex.set(prevIndex);
  }

  /**
   * Gets the total number of available background images
   */
  getTotalImages(): number {
    return this.backgroundImages.length;
  }

  /**
   * Gets the current image index
   */
  getCurrentImageIndex(): number {
    return this.currentImageIndex();
  }
}
