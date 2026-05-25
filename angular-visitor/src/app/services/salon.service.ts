import { Injectable, signal, inject, OnDestroy } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ChatApiService, PollEvent } from './chat-api.service';

export interface TimeSlot { time: string; available: boolean; }
export interface ChatMessage { role: 'ai'|'user'|'staff'|'system'; text: string; actions?: ChatAction[]; }
export interface ChatAction { label: string; type: string; payload?: any; }
export type StaffState = 'idle' | 'offering' | 'connected';

@Injectable({ providedIn: 'root' })
export class SalonService implements OnDestroy {
  private api = inject(ChatApiService);

  readonly staffState = signal<StaffState>('idle');
  readonly messages = signal<ChatMessage[]>([]);
  readonly connectionStatus = signal<'connecting'|'connected'|'error'>('connecting');

  private sid = '';
  private seq = 0;
  private timer: any = null;

  constructor() { this.connect(); }
  ngOnDestroy() { if (this.timer) clearTimeout(this.timer); }

  // ── connect ──

  private async connect() {
    this.connectionStatus.set('connecting');
    try {
      const stored = sessionStorage?.getItem('ace_sid') || '';
      const res = await firstValueFrom(this.api.sendMessage(stored || undefined, ''));
      this.sid = res.sid;
      sessionStorage?.setItem('ace_sid', res.sid);
      this.connectionStatus.set('connected');
      if (!stored && (res.reply || res.currentStep?.title)) {
        this.add('ai', res.reply || res.currentStep!.title, this.defaultActions());
      }
      await this.loadHistory();
    } catch {
      sessionStorage?.removeItem('ace_sid');
      this.connectionStatus.set('connected');
      this.add('ai', this.defaultGreeting(), this.defaultActions());
    }
    this.poll();
  }

  private async loadHistory() {
    if (!this.sid) return;
    try {
      const t = await firstValueFrom(this.api.getThread(this.sid));
      if (t.length) {
        const msgs: ChatMessage[] = t.map(m => ({
          role: (m.role === 'staff' ? 'staff' : m.role === 'user' ? 'user' : 'ai') as ChatMessage['role'],
          text: m.text,
        }));
        this.messages.set(msgs);
        if (msgs.some(m => m.role === 'staff')) this.staffState.set('connected');
      }
    } catch { /* ignore */ }
  }

  // ── poll ──

  private poll() {
    if (!this.sid) { this.timer = setTimeout(() => this.poll(), 3000); return; }
    this.api.pollEvents(this.sid, this.seq).subscribe({
      next: r => {
        for (const e of r.events) this.handle(e);
        this.seq = r.next;
        this.timer = setTimeout(() => this.poll(), 3000);
      },
      error: () => { this.timer = setTimeout(() => this.poll(), 3000); }
    });
  }

  private handle(e: PollEvent) {
    const p = (e as any).payload;
    switch (e.type) {
      case 'lead.takeover.started':
        this.staffState.set('connected');
        break;
      case 'lead.takeover.ended':
        this.staffState.set('idle');
        this.add('ai', 'Pogovor z osebjem se je zaključil. Še vedno sem tukaj, da vam pomagam.', this.defaultActions());
        break;
      case 'message.created':
        if (!p?.text || p.role === 'user') break;
        if (this.messages().some(m => m.text === p.text)) break;
        if (p.role === 'staff') { this.staffState.set('connected'); this.add('staff', p.text); }
        else if (p.role === 'assistant' && this.staffState() === 'idle') { this.add('ai', p.text); }
        break;
    }
  }

  // ── send ──

  async sendMessage(text: string) {
    this.add('user', text);
    try {
      const res = await firstValueFrom(this.api.sendMessage(this.sid, text));
      this.sid = res.sid;
      if (this.staffState() === 'connected') {
        if (res.reply) { this.staffState.set('idle'); this.add('ai', res.reply, this.defaultActions()); }
        return;
      }
      if (res.reply || res.currentStep?.title) {
        this.add('ai', res.reply || res.currentStep!.title, res.storyComplete ? [] : this.defaultActions());
      }
      if (res.storyComplete && res.completionTitle) this.add('ai', res.completionTitle);
    } catch (e: any) {
      this.add('system', 'Strežnik trenutno ni dosegljiv.');
    }
  }

  // ── helpers ──

  add(role: ChatMessage['role'], text: string, actions?: ChatAction[]) {
    this.messages.update(msgs => [...msgs, { role, text, actions }]);
  }

  defaultGreeting() { return 'Dober dan! Dobrodošli. Kako vam lahko pomagamo? 💆‍♀️'; }
  defaultActions(): ChatAction[] { return [
    { label: '🎥 Prosim osebje', type: 'request-staff' },
    { label: '📅 Rezerviraj termin', type: 'book-appointment' },
  ];}

  // ── staff handoff ──
  staffOffering() { this.staffState.set('offering'); this.add('system', 'Osebje je na voljo.', [
    { label: '✅ Sprejmi', type: 'accept-staff' }, { label: '❌ Ne, hvala', type: 'deny-staff' },
  ]);}
  acceptStaff() { this.staffState.set('connected'); this.add('system', 'Povezani ste z osebjem.'); }
  denyStaff()  { this.staffState.set('idle'); this.add('ai', 'Ni problema! Še vedno sem tukaj.', this.defaultActions()); }

  // ── stubs for components ──
  readonly salonName = 'Lepota & Sprostitev';
  readonly salonSubtitle = 'Kozmetični salon';
  readonly openHour = '09:00';
  readonly closeHour = '18:00';
  readonly status = signal<'open'|'closed'>('open');
  readonly errorMessage = signal<string|null>(null);
  readonly selectedService = signal<any>(null);
  readonly selectedDate = signal<string|null>(null);
  readonly selectedSlot = signal<string|null>(null);
  services = [{id:'nega-obraza',name:'Nega obraza',durationMin:45,priceEur:35,imageUrl:''}];
  addMessage(m: ChatMessage) { this.add(m.role, m.text, m.actions); }
  getSlotsForDate(_: string) { return [{time:'09:00',available:true}]; }
  requestStaff() { if (this.status()==='open') this.staffOffering(); else this.add('ai','Trenutno smo zaprti.'); }
}
