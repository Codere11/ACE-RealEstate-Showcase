import { Component, signal, computed } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

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
    this.activePersona.set(p);
  }

  send() {
    const text = this.inputText.trim();
    if (!text || !this.activePersona()) return;

    const persona = this.activePersona()!;
    this.messages.update(msgs => [...msgs, { role: 'user', text, time: new Date() }]);
    this.inputText = '';
    this.sending = true;

    // Stub: simulate AI response after a short delay
    // Backend will be wired later
    setTimeout(() => {
      this.messages.update(msgs => [
        ...msgs,
        {
          role: 'ai',
          text: `[${persona.name} bo odgovoril/a tukaj — backend še ni povezan.]`,
          time: new Date(),
        },
      ]);
      this.sending = false;
    }, 600);
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }
}
