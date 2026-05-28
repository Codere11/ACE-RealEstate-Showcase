import { Injectable, signal, inject, OnDestroy, NgZone, ApplicationRef } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ChatApiService, PollEvent } from './chat-api.service';

export interface TimeSlot { time: string; available: boolean; }
export interface ChatMessage { id?: string; role: 'ai'|'user'|'staff'|'system'; text: string; actions?: ChatAction[]; }
export interface ChatAction { label: string; type: string; payload?: any; }
export type StaffState = 'idle' | 'offering' | 'connected';

let _msgId = 0;
function nextId(): string { return 'm' + (++_msgId); }

@Injectable({ providedIn: 'root' })
export class SalonService implements OnDestroy {
  onStaffMessage: (() => void) | null = null;
  private api = inject(ChatApiService);
  private zone = inject(NgZone);
  private appRef = inject(ApplicationRef);

  readonly staffState = signal<StaffState>('idle');
  readonly messages = signal<ChatMessage[]>([]);
  readonly connectionStatus = signal<'connecting'|'connected'|'error'>('connecting');
  readonly status = signal<'open'|'closed'>('open');
  readonly errorMessage = signal<string|null>(null);
  readonly aiLoading = signal(false);  // true while waiting for AI reply

  private sid = '';
  private seq = 0;
  private timer: any = null;

  constructor() { this.updateStatus(); setInterval(() => this.updateStatus(), 30_000); this.connect(); }
  ngOnDestroy() { if (this.timer) clearTimeout(this.timer); }

  private updateStatus() {
    const m = new Date().getHours() * 60 + new Date().getMinutes();
    this.status.set(m >= 540 && m < 1080 ? 'open' : 'closed');
  }

  // ══════ CONNECT ══════

  private async connect() {
    this.connectionStatus.set('connecting');
    try {
      const stored = sessionStorage?.getItem('ace_sid') || '';
      const res = await firstValueFrom(this.api.sendMessage(stored || undefined, ''));
      this.sid = res.sid; sessionStorage?.setItem('ace_sid', res.sid);
      this.connectionStatus.set('connected');
      await this.loadHistory();
      // Only add greeting if history is empty (prevents double-greeting)
      if (this.messages().length === 0 && (res.reply || res.currentStep?.title)) {
        this.addMsg('ai', res.reply || res.currentStep!.title);
      }
    } catch {
      sessionStorage?.removeItem('ace_sid');
      this.connectionStatus.set('connected');
      if (this.messages().length === 0) this.addMsg('ai', this.defaultGreeting());
    }
    this.startPolling();
  }

  private async loadHistory() {
    if (!this.sid) return;
    try {
      const t = await firstValueFrom(this.api.getThread(this.sid));
      if (t.length) {
        const msgs: ChatMessage[] = t.map(m => ({
          id: nextId(),
          role: (m.role === 'staff' ? 'staff' : m.role === 'user' ? 'user' : 'ai') as ChatMessage['role'],
          text: m.text,
        }));
        this.messages.set(msgs);
        if (msgs.some(m => m.role === 'staff')) this.staffState.set('connected');
      }
    } catch {}
  }

  // ══════ SSE ══════

  private startPolling() {
    if (!this.sid) { this.timer = setTimeout(() => this.startPolling(), 2000); return; }
    this.doPoll();
  }
  private doPoll() {
    if (!this.sid) return;
    this.api.pollEvents(this.sid, this.seq).subscribe({
      next: r => { this.zone.run(() => { for (const e of r.events) this.onEvent(e); this.seq = r.next; }); },
      error: () => {}
    });
    this.timer = setTimeout(() => this.doPoll(), 1000);
  }

  private onEvent(e: PollEvent) {
    const p = (e as any).payload;
    switch (e.type) {
      case 'lead.takeover.started':
        this.staffState.set('connected'); break;
      case 'lead.takeover.ended':
        this.staffState.set('idle');
        this.addMsg('ai', 'Pogovor z osebjem se je zaključil.');
        break;
      case 'live_session.started':
        this.staffState.set('connected');
        if (this.onStaffMessage) this.onStaffMessage();
        break;
      case 'live_session.ended':
        this.staffState.set('idle');
        break;
      case 'message.created':
        if (!p?.text || p.role === 'user') break;
        if (p.role === 'staff') {
          this.staffState.set('connected');
          this.addMsg('staff', p.text);
          this.appRef.tick();
          if (this.onStaffMessage) this.onStaffMessage();
        } else if (p.role === 'assistant' && this.staffState() === 'idle') {
          if (!this.messages().some(m => m.text === p.text)) this.addMsg('ai', p.text);
        }
        break;
    }
  }

  // ══════ SEND ══════

  async sendMessage(text: string) {
    this.addMsg('user', text);
    const loadingId = nextId();
    this.messages.update(msgs => [...msgs, { id: loadingId, role: 'ai', text: '__LOADING__' }]);
    this.aiLoading.set(true);
    try {
      const res = await firstValueFrom(this.api.sendMessage(this.sid, text));
      this.sid = res.sid;
      // Remove loading placeholder, add reply (dedup: event might have arrived first)
      this.messages.update(msgs => {
        const withoutLoading = msgs.filter(m => m.id !== loadingId);
        if (res.reply && !withoutLoading.some(m => m.text === res.reply)) {
          return [...withoutLoading, { id: nextId(), role: 'ai' as const, text: res.reply }];
        }
        return withoutLoading;
      });
      if (res.reply && this.staffState() === 'connected') {
        this.staffState.set('idle');
      }
    } catch {
      this.messages.update(msgs => msgs.filter(m => m.id !== loadingId));
      this.addMsg('system', 'Strežnik trenutno ni dosegljiv.');
    }
    this.aiLoading.set(false);
  }

  // ══════ MESSAGES ══════

  addMsg(role: ChatMessage['role'], text: string, actions?: ChatAction[]) {
    this.messages.update(msgs => [...msgs, { id: nextId(), role, text, actions }]);
  }

  // ══════ STAFF ══════

  staffOffering() { this.staffState.set('offering'); this.addMsg('system', 'Osebje je na voljo.', [
    { label: '✅ Sprejmi', type: 'accept-staff' }, { label: '❌ Ne, hvala', type: 'deny-staff' },
  ]);}
  acceptStaff() { this.staffState.set('connected'); this.addMsg('system', 'Povezani ste z osebjem.'); }
  denyStaff()  { this.staffState.set('idle'); this.addMsg('ai', 'Ni problema!'); }
  requestStaff() {
    if (this.sid) fetch('/api/public/organizations/'+this.getTenantSlug()+'/leads/'+this.sid+'/request-staff',{method:'POST'}).catch(()=>{});
    const isClosed = this.status() !== 'open';
    if (isClosed) {
      // Let the AI handle it — LLM will understand salon is closed and ask for contact
      this.sendMessage('Prosim osebje');
    } else {
      this.staffOffering();
    }
  }

  // ══════ HELPERS ══════

  defaultGreeting() { return 'Dober dan! Dobrodošli. Kako vam lahko pomagamo? 💆‍♀️'; }

  requestStaffAction(): ChatAction { return { label: '🎥 Prosim osebje', type: 'request-staff' }; }
  private getTenantSlug(): string {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('org'); if (p) return p;
      const seg = window.location.pathname.replace(/^\/+/, '').split('/')[0]; if (seg) return seg;
    }
    return 'demo';
  }

  // ══════ STUBS ══════
  readonly salonName = 'Lepota & Sprostitev'; readonly salonSubtitle = 'Kozmetični salon';
  readonly openHour = '09:00'; readonly closeHour = '18:00';
  readonly selectedService = signal<any>(null);
  readonly selectedDate = signal<string|null>(null);
  readonly selectedSlot = signal<string|null>(null);
  services = [
    {id:'nega-obraza',name:'Nega obraza',durationMin:45,priceEur:35,imageUrl:'',
     addons:[{name:'Kolagenska maska',priceEur:15},{name:'Limfna drenaža',priceEur:20},{name:'LED terapija',priceEur:10}]},
    {id:'maska-obraza',name:'Maska obraza',durationMin:30,priceEur:25,imageUrl:'',
     addons:[{name:'Hialuronski serum',priceEur:12},{name:'Pomirjevalna krema',priceEur:8},{name:'Očesni tretma',priceEur:15}]},
    {id:'ciscenje-obraza',name:'Čiščenje obraza',durationMin:60,priceEur:50,imageUrl:'',
     addons:[{name:'Encimski piling',priceEur:18},{name:'LED terapija',priceEur:10},{name:'Kolagenska maska',priceEur:15}]},
  ];
  addMessage(m: ChatMessage) { this.addMsg(m.role, m.text, m.actions); }
  addMessageObj(m: {role: string, text: string, actions?: ChatAction[]}) { this.addMsg(m.role as ChatMessage['role'], m.text, m.actions); }
  getSlotsForDate(_: string) { return [{time:'09:00',available:true}]; }
}
