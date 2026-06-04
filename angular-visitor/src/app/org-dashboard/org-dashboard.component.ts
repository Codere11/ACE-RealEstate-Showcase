import { Component, signal, OnInit, OnDestroy, inject, ElementRef, ViewChild, NgZone } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DecimalPipe, DatePipe, JsonPipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { OrgDashboardService } from '../services/org-dashboard.service';
import { AnalizeChatComponent } from '../analize-chat/analize-chat.component';
import { firstValueFrom } from 'rxjs';
import { Room, RoomEvent, LocalVideoTrack, RemoteParticipant, RemoteTrack, RemoteTrackPublication, Track, createLocalVideoTrack } from 'livekit-client';

@Component({
  standalone: true,
  imports: [FormsModule, DecimalPipe, DatePipe, JsonPipe, AnalizeChatComponent],
  templateUrl: './org-dashboard.component.html',
  styleUrl: './org-dashboard.component.scss',
})
export class OrgDashboardComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private api = inject(OrgDashboardService);
  private zone = inject(NgZone);

  slug = signal(''); orgId = 0; error = signal('');
  leads = signal<any[]>([]); allLeads = signal<any[]>([]);
  messages = signal<any[]>([]);
  selectedSid = ''; takeoverActive = signal(false); takeoverText = '';
  activeTab = 'leads';
  showDebugData = true;
  expandedLeads = signal<Set<string>>(new Set());
  debugLoading = false;
  filters = { search: '', staffRequested: false, workingHours: true, takeoverOnly: false };

  // Rezervacije tab state — loaded from API
  bookings = signal<any[]>([]);

  // Rezervacije tab state
  bookingFilters = { search: '', service: 'all', status: 'all', hideCompleted: false };
  selectedBooking: any = null;
  editingBookingId: number | null = null;
  editingBooking: any = null;
  editField: { bookingId: number, field: string } | null = null;
  editValue = '';
  bookingView = signal<'day' | 'week'>('day');
  bookingDate = signal<string>(new Date().toISOString().slice(0, 10));
  showNewBooking = false;
  newBooking = { name: '', phone: '', email: '', service: 'nega-obraza', date: new Date().toISOString().slice(0, 10), time: '', notes: '' };
  newBookingError = '';
  bookingsLoading = false;

  // Live/camera state
  liveActive = signal(false);
  liveConnecting = signal(false);
  liveRoom: Room | null = null;

  @ViewChild('staffVideo') staffVideoEl!: ElementRef<HTMLVideoElement>;

  private timer: any = null;

  async ngOnInit() {
    this.slug.set(this.route.snapshot.paramMap.get('slug') || '');
    await this.resolveOrg();
    await this.loadLeads();
    await this.loadBookings();
    this.timer = setInterval(() => {
      this.loadLeads();
      this.loadBookings();
      if (this.selectedSid) this.select(this.selectedSid);
    }, 3000);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        this.loadLeads();
        this.loadBookings();
      }
    });
  }
  ngOnDestroy() { if (this.timer) clearInterval(this.timer); this.disconnectLive(); }

  // ══════ CAMERA / LIVE ══════

  async goLive() {
    if (!this.selectedSid || !this.orgId || this.liveConnecting()) return;
    this.liveConnecting.set(true);
    try {
      // First, send a staff takeover message so the visitor knows staff is active
      try {
        await firstValueFrom(this.api.sendTakeover(this.orgId, this.selectedSid, 'Pozdravljeni! Povezujem se preko kamere ...'));
      } catch (e) { console.warn('Takeover message failed, continuing:', e); }

      const res = await firstValueFrom(this.api.goLive(this.orgId, this.selectedSid));
      if (!res.token || !res.wsUrl) throw new Error('No token');

      // Get local camera
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      const videoTrack = stream.getVideoTracks()[0];

      // Show local preview
      if (this.staffVideoEl) {
        this.staffVideoEl.nativeElement.srcObject = stream;
        this.staffVideoEl.nativeElement.muted = true;
      }

      // Connect to LiveKit and publish
      this.liveRoom = new Room({ adaptiveStream: true, dynacast: true });
      await this.liveRoom.connect(res.wsUrl, res.token);
      const lkTrack = await createLocalVideoTrack({ deviceId: videoTrack.getSettings().deviceId });
      await this.liveRoom.localParticipant.publishTrack(lkTrack);

      this.liveActive.set(true);
      this.liveConnecting.set(false);
    } catch (e: any) {
      console.error('Go live failed:', e);
      this.liveConnecting.set(false);
      this.error.set('Camera error: ' + (e.message || 'Unknown'));
    }
  }

  async endLive() {
    if (!this.selectedSid || !this.orgId) return;
    try {
      await firstValueFrom(this.api.endLive(this.orgId, this.selectedSid));
    } catch (e) { console.error('End live API failed:', e); }
    this.disconnectLive();
  }

  private disconnectLive() {
    this.liveRoom?.disconnect();
    this.liveRoom = null;
    this.liveActive.set(false);
    this.liveConnecting.set(false);
    if (this.staffVideoEl) {
      const stream = this.staffVideoEl.nativeElement.srcObject as MediaStream;
      stream?.getTracks().forEach(t => t.stop());
      this.staffVideoEl.nativeElement.srcObject = null;
    }
  }

  async loadAllMessages() {
    if (!this.orgId || this.debugLoading) return;
    this.debugLoading = true;
    const leads = this.allLeads();
    // Load in batches of 5
    for (let i = 0; i < leads.length; i += 5) {
      const batch = leads.slice(i, i + 5);
      const batchResults = await Promise.all(
        batch.map(async (lead: any) => {
          try {
            const msgs = await firstValueFrom(this.api.getMessages(this.orgId, lead.sid));
            return { ...lead, messages: msgs };
          } catch {
            return { ...lead, messages: null };
          }
        })
      );
      // Merge into allLeads in-place
      this.allLeads.update(current => {
        const copy = [...current];
        for (const enriched of batchResults) {
          const idx = copy.findIndex(l => l.sid === enriched.sid);
          if (idx !== -1) copy[idx] = enriched;
        }
        return copy;
      });
    }
    this.debugLoading = false;
  }

  private async resolveOrg() {
    try {
      const orgs = await firstValueFrom(this.api.getOrgs());
      const org = orgs.find((o: any) => o.slug === this.slug());
      if (!org) { this.error.set('Organizacija ne obstaja. Preverite URL (trenutno: /' + this.slug() + '/dashboard).'); return; }
      this.orgId = org.id;
    } catch { this.error.set('Napaka pri povezavi s strežnikom. Preverite ce backend teče na localhost:8000.'); }
  }

  async loadLeads() {
    if (!this.orgId) return;
    try {
      let list = await firstValueFrom(this.api.getLeads(this.orgId));
      list.sort((a: any, b: any) => (b.staffRequested ? 1 : 0) - (a.staffRequested ? 1 : 0) || (b.lastSeenSec || 0) - (a.lastSeenSec || 0));
      // Preserve loaded messages across polling refreshes
      const prev = this.allLeads();
      for (const lead of list) {
        const existing = prev.find(l => l.sid === lead.sid);
        if (existing?.messages) lead.messages = existing.messages;
      }
      this.allLeads.set(list); this.applyFilters();
    } catch(e: any) { console.error(e); if (e?.status === 401) this.error.set('Prijava je potekla. <a href="/login">Prijavite se</a>.'); }
  }

  async loadBookings() {
    if (!this.orgId) return;
    try {
      const list = await firstValueFrom(this.api.getBookings(this.orgId));
      const oldIds = new Set(this.bookings().map(b => b.id));
      this.bookings.set(list.map((b: any) => ({
        ...b, status: b.status || 'confirmed', customerName: b.customerName || '',
        customerPhone: b.customerPhone || '', customerEmail: b.customerEmail || '',
        serviceId: b.serviceId, serviceName: b.serviceName, durationMin: b.durationMin, priceEur: b.priceEur,
        bookingDate: b.bookingDate, bookingTime: b.bookingTime, notes: b.notes || ''
      })));
      // Auto-navigate to first NEW booking's date (only when a genuinely new booking appears)
      for (const b of list) {
        if (!oldIds.has(b.id) && b.bookingDate !== this.bookingDate()) {
          this.bookingDate.set(b.bookingDate);
          break;
        }
      }
      // If first successful load and no bookings for today, jump to earliest booking date
      if (oldIds.size === 0 && list.length > 0 && this.todaysBookings.length === 0) {
        this.bookingDate.set(list[0].bookingDate);
      }
    } catch(e: any) { console.error('loadBookings:', e); }
  }

  applyFilters() {
    let list = this.allLeads();
    const q = this.filters.search.toLowerCase();
    if (q) list = list.filter(l => (l.name || '').toLowerCase().includes(q) || (l.sid || '').toLowerCase().includes(q));
    if (this.filters.staffRequested) list = list.filter(l => l.staffRequested);
    if (this.filters.takeoverOnly) list = list.filter(l => l.takeoverActive);
    this.leads.set(list);
  }

  async select(sid: string) {
    this.selectedSid = sid;
    const lead = this.allLeads().find(l => l.sid === sid);
    this.takeoverActive.set(lead?.takeoverActive || false);
    try {
      this.messages.set(await firstValueFrom(this.api.getMessages(this.orgId, sid)));
    } catch {}
  }

  async sendTakeover() {
    if (!this.selectedSid || !this.takeoverText.trim()) return;
    try {
      await firstValueFrom(this.api.sendTakeover(this.orgId, this.selectedSid, this.takeoverText));
      this.takeoverText = ''; this.takeoverActive.set(true);
      await this.loadLeads(); await this.select(this.selectedSid);
    } catch {}
  }

  async endTakeover() {
    if (!this.selectedSid) return;
    try {
      await firstValueFrom(this.api.endTakeover(this.orgId, this.selectedSid));
      this.takeoverActive.set(false); await this.loadLeads(); await this.select(this.selectedSid);
    } catch {}
  }

  async deleteLead(sid: string) {
    if (!confirm('Delete this lead?')) return;
    try {
      await firstValueFrom(this.api.deleteLead(this.orgId, sid));
      if (sid === this.selectedSid) { this.selectedSid = ''; this.messages.set([]); this.takeoverActive.set(false); }
      await this.loadLeads();
    } catch {}
  }

  async deleteSelected() { await this.deleteLead(this.selectedSid); }

  selectedLeadName() { return this.allLeads().find(l => l.sid === this.selectedSid)?.name || 'Visitor'; }
  get now() { return new Date().toISOString(); }
  toggleLead(sid: string) {
    this.expandedLeads.update(set => {
      const next = new Set(set);
      if (next.has(sid)) next.delete(sid); else next.add(sid);
      return next;
    });
  }

  isExpanded(sid: string): boolean {
    return this.expandedLeads().has(sid);
  }

  // ══════ REZERVACIJE HELPERS ══════

  get todaysBookings() { const d = this.bookingDate(); return this.bookings().filter(b => b.bookingDate === d); }
  get filteredBookings() {
    let list = this.todaysBookings;
    const q = this.bookingFilters.search.toLowerCase();
    if (q) list = list.filter(b => b.customerName.toLowerCase().includes(q));
    if (this.bookingFilters.service !== 'all') list = list.filter(b => b.serviceId === this.bookingFilters.service);
    if (this.bookingFilters.status !== 'all') list = list.filter(b => b.status === this.bookingFilters.status);
    if (this.bookingFilters.hideCompleted) list = list.filter(b => b.status !== 'completed');
    return list.sort((a, b) => a.bookingTime.localeCompare(b.bookingTime));
  }
  get bookingStats() {
    const all = this.bookings().filter(b => b.bookingDate === this.bookingDate());
    return { count: all.length, totalMin: all.reduce((s, b) => s + b.durationMin, 0), totalEur: all.filter(b => b.status !== 'cancelled').reduce((s, b) => s + b.priceEur, 0), confirmed: all.filter(b => b.status === 'confirmed' || b.status === 'in_progress').length, cancelled: 0 };
  }
  get weekStats() { return { count: this.bookings().length, confirmed: this.bookings().filter(b => b.status === 'confirmed' || b.status === 'in_progress').length, inProgress: this.bookings().filter(b => b.status === 'in_progress').length, completed: this.bookings().filter(b => b.status === 'completed').length, noShow: this.bookings().filter(b => b.status === 'no_show').length }; }
  get allServices() { return [{ id: 'nega-obraza', name: 'Nega obraza (45 min, 35€)' }, { id: 'maska-obraza', name: 'Maska obraza (30 min, 25€)' }, { id: 'ciscenje-obraza', name: 'Čiščenje obraza (60 min, 50€)' }]; }
  timeSlots = ['09:00','09:30','10:00','10:30','11:00','11:30','12:00','13:00','13:30','14:00','14:30','15:00','15:30','16:00','16:30','17:00','17:30'];
  get freeSlots() { const taken = this.todaysBookings.map(b => b.bookingTime); return this.timeSlots.filter(t => !taken.includes(t) && t !== '12:00'); }

  getBookingAt(time: string) { return this.todaysBookings.find(b => b.bookingTime === time); }
  statusLabel(s: string) { const m: any = { confirmed: 'Potrjeno', in_progress: 'V teku', completed: 'Končano', no_show: 'Ni prišel/-a', cancelled: 'Odpovedano' }; return m[s] || s; }
  statusPillClass(s: string) { const m: any = { confirmed: '', in_progress: 'warn', completed: 'success', no_show: 'dark', cancelled: 'dark' }; return m[s] || 'dark'; }
  bookingDot(s: string) { const m: any = { confirmed: '●', in_progress: '◉', completed: '○', no_show: '✕', cancelled: '—' }; return m[s] || '●'; }

  selectBooking(b: any) { if (this.editingBookingId === b.id) return; this.selectedBooking = this.selectedBooking?.id === b.id ? null : b; this.cancelEdit(); }
  startEdit(b: any) { this.editingBookingId = b.id; this.editingBooking = { ...b }; }
  saveEdit() {
    if (!this.editingBooking) return;
    const b = this.bookings().find(x => x.id === this.editingBookingId);
    if (b) { Object.assign(b, this.editingBooking); this.bookings.set([...this.bookings()]); }
    this.cancelEdit();
  }
  cancelEdit() { this.editingBookingId = null; this.editingBooking = null; }

  // Inline field editing
  startEditField(b: any, field: string, event: Event) {
    event.stopPropagation();
    this.editField = { bookingId: b.id, field };
    this.editValue = (b as any)['customer' + (field === 'name' ? 'Name' : field === 'phone' ? 'Phone' : field === 'email' ? 'Email' : field === 'notes' ? 'Notes' : '')] || (b as any)[field] || '';
  }
  saveEditField() {
    if (!this.editField) return;
    const b = this.bookings().find(x => x.id === this.editField!.bookingId);
    if (!b) { this.editField = null; return; }
    const f = this.editField.field;
    if (f === 'name') b.customerName = this.editValue;
    else if (f === 'phone') b.customerPhone = this.editValue;
    else if (f === 'email') b.customerEmail = this.editValue;
    else if (f === 'notes') b.notes = this.editValue;
    else if (f === 'time') b.bookingTime = this.editValue;
    else if (f === 'service') { b.serviceId = this.editValue; this.onEditServiceChangeInline(b); }
    this.bookings.set([...this.bookings()]);
    this.editField = null;
  }
  cancelEditField() { this.editField = null; }
  onEditServiceChangeInline(b: any) {
    const sid = b.serviceId;
    b.serviceName = sid === 'nega-obraza' ? 'Nega obraza' : sid === 'maska-obraza' ? 'Maska obraza' : 'Čiščenje obraza';
    b.durationMin = sid === 'nega-obraza' ? 45 : sid === 'maska-obraza' ? 30 : 60;
    b.priceEur = sid === 'nega-obraza' ? 35 : sid === 'maska-obraza' ? 25 : 50;
  }
  deleteBooking(b: any) { this.api.deleteBooking(this.orgId, b.id).subscribe({ next: () => this.loadBookings(), error: () => {} }); this.selectedBooking = null; this.cancelEdit(); }
  weekDays() { const [y,m,day] = this.bookingDate().split('-').map(Number); const d = new Date(Date.UTC(y, m-1, day)); const dow = d.getUTCDay(); const mon = new Date(Date.UTC(y, m-1, day - (dow === 0 ? 6 : dow - 1))); return Array.from({ length: 6 }, (_, i) => { const dt = new Date(mon); dt.setUTCDate(mon.getUTCDate() + i); return dt.toISOString().slice(0, 10); }); }
  weekDayLabel(d: string) { const [y,m,day] = d.split('-').map(Number); const dt = new Date(Date.UTC(y, m-1, day)); const n = ['PO','TO','SR','ČE','PE','SO'][dt.getUTCDay() - 1] || '??'; return n + ' ' + String(day) + '.'; }
  getWeekBooking(date: string, time: string) { return this.bookings().find(b => b.bookingDate === date && b.bookingTime === time); }

  addDays(dateStr: string, n: number) { const [y,m,d] = dateStr.split('-').map(Number); const dt = new Date(Date.UTC(y, m-1, d + n)); return dt.toISOString().slice(0, 10); }
  prevDay() { this.bookingDate.set(this.addDays(this.bookingDate(), -1)); this.selectedBooking = null; }
  nextDay() { this.bookingDate.set(this.addDays(this.bookingDate(), 1)); this.selectedBooking = null; }
  goToday() { this.bookingDate.set(new Date().toISOString().slice(0, 10)); this.selectedBooking = null; }
  toggleBookingView() { this.bookingView.set(this.bookingView() === 'day' ? 'week' : 'day'); }
  todayStr() { return new Date().toISOString().slice(0, 10); }

  // ══════ DRAG & DROP ══════

  onDragStart(e: DragEvent, b: any) { e.dataTransfer!.setData('text/plain', String(b.id)); e.dataTransfer!.effectAllowed = 'move'; (e.target as HTMLElement).closest('.booking-card')?.classList.add('dragging'); }
  onDragEnd(e: DragEvent) { document.querySelectorAll('.dragging').forEach(el => el.classList.remove('dragging')); }
  onDragOver(e: DragEvent) { e.preventDefault(); e.dataTransfer!.dropEffect = 'move'; const t = e.currentTarget as HTMLElement; (t.querySelector('.booking-slot-empty') || t.closest('.booking-card') || t).classList.add('drag-hover'); }
  onDragLeave(e: DragEvent) { const t = e.currentTarget as HTMLElement; (t.querySelector('.booking-slot-empty') || t.closest('.booking-card') || t).classList.remove('drag-hover'); }
  onDrop(e: DragEvent, time: string) {
    e.preventDefault();
    e.stopPropagation();
    (e.currentTarget as HTMLElement).querySelector('.booking-slot-empty')?.classList.remove('drag-hover');
    (e.currentTarget as HTMLElement).closest('.booking-card')?.classList.remove('drag-hover');
    document.querySelectorAll('.dragging').forEach(el => el.classList.remove('dragging'));
    const id = parseInt(e.dataTransfer!.getData('text/plain'));
    const dragged = this.bookings().find(x => x.id === id);
    if (!dragged) return;
    const existing = this.getBookingAt(time);
    if (existing && existing.id !== id) {
      // Swap: move existing to dragged's slot
      existing.bookingTime = dragged.bookingTime;
    }
    dragged.bookingTime = time;
    this.bookings.set([...this.bookings()]);
  }

  // ══════ NEW BOOKING ══════

  get newBookingValid() { return this.newBooking.name.trim() && this.newBooking.time && (this.newBooking.phone.trim() || this.newBooking.email.trim()); }
  addBooking() {
    if (!this.newBookingValid) { this.newBookingError = 'Ime, ura in vsaj en kontakt (telefon ali email) so obvezni.'; return; }
    this.api.createBooking(this.orgId, {
      customer_name: this.newBooking.name.trim(), customer_phone: this.newBooking.phone.trim(),
      customer_email: this.newBooking.email.trim(), service_id: this.newBooking.service,
      booking_date: this.newBooking.date, booking_time: this.newBooking.time, notes: this.newBooking.notes
    }).subscribe({
      next: () => { this.loadBookings(); this.showNewBooking = false; this.newBookingError = '';
        this.newBooking = { name: '', phone: '', email: '', service: 'nega-obraza', date: new Date().toISOString().slice(0, 10), time: '', notes: '' }; },
      error: (e) => { this.newBookingError = e?.error?.detail || 'Napaka pri rezervaciji.'; }
    });
  }
  onEditServiceChange() {
    if (!this.editingBooking) return;
    const sid = this.editingBooking.serviceId;
    this.editingBooking.serviceName = sid === 'nega-obraza' ? 'Nega obraza' : sid === 'maska-obraza' ? 'Maska obraza' : 'Čiščenje obraza';
    this.editingBooking.durationMin = sid === 'nega-obraza' ? 45 : sid === 'maska-obraza' ? 30 : 60;
    this.editingBooking.priceEur = sid === 'nega-obraza' ? 35 : sid === 'maska-obraza' ? 25 : 50;
  }

  get visibleCount() { return this.leads().length; }
  get leadCount() { return this.allLeads().length; }
  get takeoverCount() { return this.allLeads().filter(l => l.takeoverActive).length; }
  get staffRequestedCount() { return this.allLeads().filter(l => l.staffRequested).length; }
  get contactCount() { return this.allLeads().filter(l => l.phone || l.email).length; }
  get openChatCount() { return this.allLeads().filter(l => l.status === 'OPEN_CHAT').length; }
  get humanCount() { return this.allLeads().filter(l => l.status === 'HUMAN_TAKEOVER').length; }

}
