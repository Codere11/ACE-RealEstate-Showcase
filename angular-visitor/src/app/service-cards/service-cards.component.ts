import { Component, inject } from '@angular/core';
import { SalonService } from '../services/salon.service';

@Component({
  selector: 'app-service-cards',
  standalone: true,
  templateUrl: './service-cards.component.html',
  styleUrls: ['./service-cards.component.scss'],
})
export class ServiceCardsComponent {
  readonly salon = inject(SalonService);

  onBook(serviceId: string): void {
    const s = this.salon.services.find(svc => svc.id === serviceId);
    if (s) {
      this.salon.selectedService.set(s);
      this.salon.addMessage({
        role: 'ai',
        text: `Odlična izbira! ${s.name} traja ${s.durationMin} min in stane ${s.priceEur} €. Želite rezervirati termin?`,
        actions: [{ label: '📅 Rezerviraj termin', type: 'book-appointment' }],
      });
      // Scroll to chat
      document.querySelector('app-receptionist-chat')?.scrollIntoView({ behavior: 'smooth' });
    }
  }
}
