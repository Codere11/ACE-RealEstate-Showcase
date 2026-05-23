import { Component, inject } from '@angular/core';
import { SalonService } from '../services/salon.service';

@Component({
  selector: 'app-staff-video',
  standalone: true,
  templateUrl: './staff-video.component.html',
  styleUrls: ['./staff-video.component.scss'],
})
export class StaffVideoComponent {
  readonly salon = inject(SalonService);
}
