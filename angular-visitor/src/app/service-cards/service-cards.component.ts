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

  onCardClick(serviceId: string): void {
    const s = this.salon.services.find(svc => svc.id === serviceId);
    if (s) {
      this.salon.addMessage({
        role: 'ai',
        text: `Zanima vas naša storitev »${s.name}«. Povejte več o vaših potrebah, pa vam povemo, kako vam lahko ACE pomaga.`,
      });
      document.querySelector('app-receptionist-chat')?.scrollIntoView({ behavior: 'smooth' });
    }
  }

  descFor(id: string): string {
    const descs: Record<string, string> = {
      'ai-reception': 'Automate visitor qualification, booking & handoff',
      'analytics': 'Real-time dashboard, conversion metrics, insights',
      'integrations': 'LiveKit video, calendar sync, payment processing',
      'lead-scoring': 'Auto-prioritize leads by intent, budget & fit',
    };
    return descs[id] || '';
  }
}
