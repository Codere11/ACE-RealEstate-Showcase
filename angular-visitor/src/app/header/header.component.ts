import { Component, inject } from '@angular/core';
import { SalonService } from '../services/salon.service';

@Component({
  selector: 'app-header',
  standalone: true,
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
})
export class HeaderComponent {
  readonly salon = inject(SalonService);
}
