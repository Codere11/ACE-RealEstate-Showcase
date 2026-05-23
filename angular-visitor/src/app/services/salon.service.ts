import { Injectable, signal, inject, OnDestroy } from '@angular/core';
import { Subscription, firstValueFrom } from 'rxjs';
import { ChatApiService, ChatResponse, PollEvent } from './chat-api.service';

export interface ServiceItem {
  id: string;
  name: string;
  durationMin: number;
  priceEur: number;
  imageUrl: string;
}

export interface TimeSlot {
  time: string;
  available: boolean;
}

export interface ChatMessage {
  role: 'ai' | 'user' | 'system';
  text: string;
  actions?: ChatAction[];
}

export interface ChatAction {
  label: string;
  type: 'request-staff' | 'book-appointment' | 'accept-staff' | 'deny-staff' | 'select-slot';
  payload?: any;
}

export type SalonStatus = 'open' | 'closed';
export type StaffState = 'idle' | 'offering' | 'joining' | 'connected';
export type ConnectionStatus = 'connecting' | 'connected' | 'error';

@Injectable({ providedIn: 'root' })
export class SalonService implements OnDestroy {
  private readonly api = inject(ChatApiService);

  // Salon config (hardcoded for demo)
  readonly salonName = 'Lepota & Sprostitev';
  readonly salonSubtitle = 'Kozmetični salon';
  readonly openHour = '09:00';
  readonly closeHour = '18:00';

  readonly services: ServiceItem[] = [
    { id: 'nega-obraza', name: 'Nega obraza', durationMin: 45, priceEur: 35, imageUrl: '' },
    { id: 'maska-obraza', name: 'Maska obraza', durationMin: 30, priceEur: 25, imageUrl: '' },
    { id: 'ciscenje-obraza', name: 'Čiščenje obraza', durationMin: 60, priceEur: 50, imageUrl: '' },
  ];

  // Reactive state
  readonly status = signal<SalonStatus>('open');
  readonly staffState = signal<StaffState>('idle');
  readonly messages = signal<ChatMessage[]>([]);
  readonly selectedService = signal<ServiceItem | null>(null);
  readonly selectedDate = signal<string | null>(null);
  readonly selectedSlot = signal<string | null>(null);
  readonly connectionStatus = signal<ConnectionStatus>('connecting');
  readonly errorMessage = signal<string | null>(null);

  // Internal state
  private sid: string | undefined;
  private pollSince = 0;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private pollSub: Subscription | null = null;

  constructor() {
    this.updateStatus();
    setInterval(() => this.updateStatus(), 30_000);

    // Connect on startup
    this.connect();
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  // --- Connection ---

  private async connect(): Promise<void> {
    this.connectionStatus.set('connecting');
    this.errorMessage.set(null);

    try {
      // Fetch initial greeting from backend
      const response = await firstValueFrom(this.api.sendMessage(undefined, ''));
      this.sid = response.sid;
      this.connectionStatus.set('connected');
      this.errorMessage.set(null);

      // Add AI greeting
      this.addMessage({
        role: 'ai',
        text: response.reply || this.getDefaultGreeting(),
        actions: this.getDefaultActions(),
      });

      // Start polling for events
      this.startPolling();

      // Fetch message history
      this.loadHistory();
    } catch (err: any) {
      console.error('[Salon] Connection failed:', err.message);
      this.connectionStatus.set('error');
      this.errorMessage.set(err.message || 'Povezava s strežnikom ni uspela.');

      // Fallback: show offline greeting
      this.addMessage({
        role: 'ai',
        text: this.getDefaultGreeting(),
        actions: this.getDefaultActions(),
      });
    }
  }

  private async loadHistory(): Promise<void> {
    if (!this.sid) return;
    try {
      const thread = await firstValueFrom(this.api.getThread(this.sid));
      if (thread.length > 0) {
        // Clear initial greeting and replace with history
        const historyMessages: ChatMessage[] = thread.map((msg) => ({
          role: msg.role as ChatMessage['role'],
          text: msg.text,
        }));
        this.messages.set(historyMessages);

        // If no message has actions, add default actions to the last AI message
        if (!historyMessages.some((m) => m.actions?.length)) {
          const lastAi = [...historyMessages].reverse().find((m) => m.role === 'ai');
          if (lastAi) {
            lastAi.actions = this.getDefaultActions();
            this.messages.set([...historyMessages]);
          }
        }
      }
    } catch (err) {
      console.warn('[Salon] Could not load history:', err);
    }
  }

  // --- Polling for real-time events ---

  private startPolling(): void {
    this.stopPolling();
    this.pollTimer = setInterval(() => this.poll(), 5000);
  }

  private stopPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    this.pollSub?.unsubscribe();
    this.pollSub = null;
  }

  private poll(): void {
    if (!this.sid) return;
    this.pollSub = this.api.pollEvents(this.sid, this.pollSince).subscribe({
      next: (result) => {
        if (result.events.length > 0) {
          for (const event of result.events) {
            this.handleEvent(event);
          }
          this.pollSince = result.next;
        }
      },
    });
  }

  private handleEvent(event: PollEvent): void {
    switch (event.type) {
      case 'lead.takeover.started':
        this.staffState.set('offering');
        this.addMessage({
          role: 'system',
          text: 'Ena od naših strokovnjakinj je na voljo, da se vam pridruži. Želite, da se poveže z vami?',
          actions: [
            { label: '✅ Sprejmi', type: 'accept-staff' },
            { label: '❌ Ne, hvala', type: 'deny-staff' },
          ],
        });
        break;

      case 'lead.takeover.ended':
        this.staffState.set('idle');
        this.addMessage({
          role: 'ai',
          text: 'Pogovor z osebjem se je zaključil. Še vedno sem tukaj, da vam pomagam. 😊',
          actions: this.getDefaultActions(),
        });
        break;

      case 'lead.touched':
        // Update lead status
        if (event['takeover_active'] === true && this.staffState() === 'idle') {
          // Staff is actively talking
        }
        break;
    }
  }

  // --- Messaging ---

  async sendMessage(text: string): Promise<void> {
    this.addMessage({ role: 'user', text });
    this.errorMessage.set(null);

    try {
      const response = await firstValueFrom(this.api.sendMessage(this.sid, text));
      this.sid = response.sid;

      this.addMessage({
        role: 'ai',
        text: response.reply || 'Oprostite, nekaj je šlo narobe. Poskusite znova.',
        actions: response.storyComplete ? [] : this.getDefaultActions(),
      });

      // Handle story complete (booking confirmed, etc.)
      if (response.storyComplete) {
        this.addMessage({
          role: 'ai',
          text: response.completionTitle || 'Hvala! Vaš termin je potrjen.',
        });
      }
    } catch (err: any) {
      console.error('[Salon] Send failed:', err.message);
      this.errorMessage.set(err.message || 'Sporočila ni bilo mogoče poslati.');

      this.addMessage({
        role: 'system',
        text: '⚠️ Strežnik trenutno ni dosegljiv. Poskusite znova čez nekaj trenutkov.',
      });
    }
  }

  addMessage(msg: ChatMessage): void {
    this.messages.update((msgs) => [...msgs, msg]);
  }

  // --- Staff handoff ---

  staffOffering(): void {
    this.staffState.set('offering');
    this.addMessage({
      role: 'system',
      text: 'Ena od naših strokovnjakinj je na voljo, da se vam pridruži. Želite, da se poveže z vami?',
      actions: [
        { label: '✅ Sprejmi', type: 'accept-staff' },
        { label: '❌ Ne, hvala', type: 'deny-staff' },
      ],
    });
  }

  acceptStaff(): void {
    this.staffState.set('joining');
    this.addMessage({
      role: 'system',
      text: 'Maja se vam pridružuje...',
    });
    setTimeout(() => {
      this.staffState.set('connected');
      this.addMessage({
        role: 'ai',
        text: 'Živjo! Sem Maja, kako vam lahko pomagam danes? ☺️',
      });
    }, 2000);
  }

  denyStaff(): void {
    this.staffState.set('idle');
    this.addMessage({
      role: 'ai',
      text: 'Ni problema! Še vedno sem tukaj, da vam pomagam. Kar povejte, kaj vas zanima. 😊',
      actions: this.getDefaultActions(),
    });
  }

  requestStaff(): void {
    if (this.status() === 'closed') {
      this.addMessage({
        role: 'ai',
        text: 'Trenutno smo zaprti in osebje ni na voljo. Lahko pa vam pomagam pri osnovnih stvareh ali rezervaciji termina za jutri! 📅',
        actions: [{ label: '📅 Rezerviraj termin', type: 'book-appointment' }],
      });
      return;
    }
    this.staffOffering();
  }

  // --- Helpers ---

  getDefaultGreeting(): string {
    if (this.status() === 'closed') {
      return `Dober večer! 👋\n\nTrenutno smo ZAPRTI, a jaz sem tukaj, da vam pomagam pri osnovnih stvareh — vprašanja o storitvah, cenah, ali pa kar rezervacija termina za jutri! 📅`;
    }
    return `Dober dan! Dobrodošli v ${this.salonName}. 💆‍♀️\n\nTrenutno smo ODPRTI — če želite, vas lahko povežem s človekom.\n\nPri nas lahko izbirate med:\n• Nega obraza (45 min, 35 €)\n• Maska obraza (30 min, 25 €)\n• Čiščenje obraza (60 min, 50 €)\n\nKako vam lahko pomagam danes?`;
  }

  getDefaultActions(): ChatAction[] {
    if (this.status() === 'closed') {
      return [{ label: '📅 Rezerviraj termin', type: 'book-appointment' }];
    }
    return [
      { label: '🎥 Prosim osebje', type: 'request-staff' },
      { label: '📅 Rezerviraj termin', type: 'book-appointment' },
    ];
  }

  private updateStatus(): void {
    const now = new Date();
    const [oh, om] = this.openHour.split(':').map(Number);
    const [ch, cm] = this.closeHour.split(':').map(Number);
    const openMin = oh * 60 + om;
    const closeMin = ch * 60 + cm;
    const nowMin = now.getHours() * 60 + now.getMinutes();
    this.status.set(nowMin >= openMin && nowMin < closeMin ? 'open' : 'closed');
  }

  getGreeting(): string {
    return this.getDefaultGreeting();
  }

  getSlotsForDate(date: string): TimeSlot[] {
    const slots: TimeSlot[] = [];
    const service = this.selectedService();
    const duration = service ? service.durationMin : 45;
    for (let h = 9; h < 18; h++) {
      for (let m = 0; m < 60; m += duration) {
        const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
        const available = !(h === 12 && m === 0);
        slots.push({ time, available });
      }
    }
    return slots;
  }
}
