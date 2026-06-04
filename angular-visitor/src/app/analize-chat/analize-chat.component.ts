import { Component, signal, computed, Input, inject } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { OrgDashboardService } from '../services/org-dashboard.service';
import { firstValueFrom } from 'rxjs';

interface Message {
  role: 'user' | 'ai';
  text: string;
  time: Date;
}

interface Persona {
  id: string;
  emoji: string;
  name: string;
  subtitle: string;
  section: 'advisor' | 'customer';
}

@Component({
  selector: 'app-analize-chat',
  standalone: true,
  imports: [FormsModule, DatePipe, JsonPipe],
  templateUrl: './analize-chat.component.html',
  styleUrl: './analize-chat.component.scss',
})
export class AnalizeChatComponent {
  private api = inject(OrgDashboardService);

  @Input() orgId = 0;
  @Input() leads: any[] = [];
  @Input() labelProgress = '';  // e.g. "67/101"

  personas: Persona[] = [
    {
      id: 'poslovni',
      emoji: '💼',
      name: 'Poslovni svetovalec',
      subtitle: 'SWOT · funnel · prihodki',
      section: 'advisor',
    },
    {
      id: 'marketingar',
      emoji: '📣',
      name: 'Marketingar',
      subtitle: 'konverzije · A/B · jezik',
      section: 'advisor',
    },
    {
      id: 'cenovni-lovec',
      emoji: '👤',
      name: 'Cenovni lovec',
      subtitle: 'pogajanje · popusti · cena',
      section: 'customer',
    },
    {
      id: 'ig-brskalka',
      emoji: '👤',
      name: 'Instagram brskalka',
      subtitle: 'vizualna · radovedna · neobvezna',
      section: 'customer',
    },
    {
      id: 'vip',
      emoji: '👤',
      name: 'VIP zahtevnež',
      subtitle: 'premium · paketi · najboljše',
      section: 'customer',
    },
  ];

  activePersona = signal<Persona | null>(null);
  messages = signal<Message[]>([]);
  inputText = '';
  sending = false;
  debugOpen = signal(false);
  personaHistories: Record<string, Message[]> = {};

  // Live debug state — updates in real-time as data flows through
  debugState = computed(() => ({
    activePersona: this.activePersona(),
    messages: this.messages(),
    sending: this.sending,
    // labeled conversations will appear here as backend wires in
    labels: null,
    jobProgress: null,
  }));

  selectPersona(p: Persona) {
    // Save current persona's conversation
    const current = this.activePersona();
    if (current) {
      this.personaHistories[current.id] = [...this.messages()];
    }
    // Switch to new persona, restore their history
    this.activePersona.set(p);
    this.messages.set(this.personaHistories[p.id] || []);
  }

  formatText(text: string): string {
    // Convert **bold** to <strong>, *italic* to <em>, newlines to <br>
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }

  send() {
    const text = this.inputText.trim();
    if (!text || !this.activePersona() || !this.orgId) return;

    const persona = this.activePersona()!;
    const currentMessages = this.messages();
    this.messages.update(msgs => [...msgs, { role: 'user', text, time: new Date() }]);
    this.inputText = '';
    this.sending = true;

    firstValueFrom(this.api.personaChat(this.orgId, persona.id, text, this.leads, currentMessages))
      .then(res => {
        this.messages.update(msgs => [...msgs, { role: 'ai', text: res.reply, time: new Date() }]);
        this.sending = false;
      })
      .catch(err => {
        this.messages.update(msgs => [...msgs, { role: 'ai', text: 'Napaka: ' + (err?.message || 'neznana'), time: new Date() }]);
        this.sending = false;
      });
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }
}
