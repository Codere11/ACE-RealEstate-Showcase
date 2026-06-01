import { Component, inject } from '@angular/core';
import { SalonService } from '../services/salon.service';

@Component({
  selector: 'app-footer',
  standalone: true,
  templateUrl: './footer.component.html',
  styleUrls: ['./footer.component.scss'],
})
export class FooterComponent {
  readonly salon = inject(SalonService);
  readonly year = new Date().getFullYear();
}
