import { Component, signal, OnInit, OnDestroy, inject, ElementRef, ViewChild, NgZone } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DecimalPipe, DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { OrgDashboardService } from '../services/org-dashboard.service';
import { firstValueFrom } from 'rxjs';
import { Room, RoomEvent, LocalVideoTrack, RemoteParticipant, RemoteTrack, RemoteTrackPublication, Track, createLocalVideoTrack } from 'livekit-client';

@Component({
  standalone: true,
  imports: [FormsModule, DecimalPipe, DatePipe],
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
  filters = { search: '', interest: 'all', status: 'all', minProgress: 0, takeoverOnly: false };

  // Rezervacije tab state
  bookingFilters = { search: '', service: 'all', status: 'all', hideCompleted: false, hideCancelled: false };
  selectedBooking: any = null;
  bookingView = signal<'day' | 'week'>('day');
  bookingDate = signal<string>(new Date().toISOString().slice(0, 10));
  showNewBooking = false;
  newBooking = { name: '', phone: '', service: 'nega-obraza', date: new Date().toISOString().slice(0, 10), time: '', notes: '' };

  // Mock bookings for UI preview
  mockBookings = signal<any[]>([
    { id: 1, customerName: 'Ana Horvat', customerPhone: '040 123 456', serviceId: 'nega-obraza', serviceName: 'Nega obraza', durationMin: 45, priceEur: 35, bookingDate: new Date().toISOString().slice(0, 10), bookingTime: '09:00', status: 'confirmed', notes: '' },
    { id: 2, customerName: 'Maja Novak', customerPhone: '051 789 012', serviceId: 'ciscenje-obraza', serviceName: 'Čiščenje obraza', durationMin: 60, priceEur: 50, bookingDate: new Date().toISOString().slice(0, 10), bookingTime: '10:00', status: 'in_progress', notes: '' },
    { id: 3, customerName: 'Petra Kovač', customerPhone: '031 456 789', serviceId: 'maska-obraza', serviceName: 'Maska obraza', durationMin: 30, priceEur: 25, bookingDate: new Date().toISOString().slice(0, 10), bookingTime: '13:00', status: 'completed', notes: 'Občutljiva koža, uporabi nežnejši piling.', visitCount: 4, isRegular: true },
    { id: 4, customerName: 'Nina Zupan', customerPhone: '070 111 222', serviceId: 'nega-obraza', serviceName: 'Nega obraza', durationMin: 45, priceEur: 35, bookingDate: new Date(Date.now() + 86400000).toISOString().slice(0, 10), bookingTime: '09:00', status: 'confirmed', notes: '' },
    { id: 5, customerName: 'Peter Horvat', customerPhone: '041 333 444', serviceId: 'ciscenje-obraza', serviceName: 'Čiščenje obraza', durationMin: 60, priceEur: 50, bookingDate: new Date(Date.now() + 86400000).toISOString().slice(0, 10), bookingTime: '11:00', status: 'confirmed', notes: '' },
    { id: 6, customerName: 'Sara Bizjak', customerPhone: '040 555 666', serviceId: 'nega-obraza', serviceName: 'Nega obraza', durationMin: 45, priceEur: 35, bookingDate: new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10), bookingTime: '15:00', status: 'confirmed', notes: 'Prvič pri nas.' },
  ]);

  // Live/camera state
  liveActive = signal(false);
  liveConnecting = signal(false);
  liveRoom: Room | null = null;

  @ViewChild('staffVideo') staffVideoEl!: ElementRef<HTMLVideoElement>;

  private timer: any = null;

  async ngOnInit() {
    this.slug.set(this.route.snapshot.paramMap.get('slug') || '');
    await this.resolveOrg();
    if (this.orgId) { await this.loadLeads(); this.timer = setInterval(() => { this.loadLeads(); if (this.selectedSid) this.select(this.selectedSid); }, 1000); }
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

  private async resolveOrg() {
    try {
      const orgs = await firstValueFrom(this.api.getOrgs());
      const org = orgs.find((o: any) => o.slug === this.slug());
      if (!org) { this.error.set('Organizacija ne obstaja.'); return; }
      this.orgId = org.id;
    } catch { this.error.set('Napaka pri povezavi.'); }
  }

  async loadLeads() {
    if (!this.orgId) return;
    try {
      let list = await firstValueFrom(this.api.getLeads(this.orgId));
      list.sort((a: any, b: any) => (b.staffRequested ? 1 : 0) - (a.staffRequested ? 1 : 0) || (b.lastSeenSec || 0) - (a.lastSeenSec || 0));
      this.allLeads.set(list); this.applyFilters();
    } catch(e: any) { console.error(e); if (e?.status === 401) this.error.set('Prijava je potekla. <a href="/login">Prijavite se</a>.'); }
  }

  applyFilters() {
    let list = this.allLeads();
    const q = this.filters.search.toLowerCase();
    if (q) list = list.filter(l => (l.name || '').toLowerCase().includes(q) || (l.sid || '').toLowerCase().includes(q));
    if (this.filters.interest !== 'all') list = list.filter(l => (l.interest || '') === this.filters.interest);
    if (this.filters.status !== 'all') list = list.filter(l => l.status === this.filters.status);
    if (this.filters.minProgress > 0) list = list.filter(l => (l.surveyProgress || 0) >= this.filters.minProgress);
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

  // ══════ REZERVACIJE HELPERS ══════

  get todaysBookings() { const d = this.bookingDate(); return this.mockBookings().filter(b => b.bookingDate === d); }
  get filteredBookings() {
    let list = this.todaysBookings;
    const q = this.bookingFilters.search.toLowerCase();
    if (q) list = list.filter(b => b.customerName.toLowerCase().includes(q));
    if (this.bookingFilters.service !== 'all') list = list.filter(b => b.serviceId === this.bookingFilters.service);
    if (this.bookingFilters.status !== 'all') list = list.filter(b => b.status === this.bookingFilters.status);
    if (this.bookingFilters.hideCompleted) list = list.filter(b => b.status !== 'completed');
    if (this.bookingFilters.hideCancelled) list = list.filter(b => b.status !== 'cancelled');
    return list.sort((a, b) => a.bookingTime.localeCompare(b.bookingTime));
  }
  get bookingStats() {
    const all = this.mockBookings().filter(b => b.bookingDate === this.bookingDate());
    return { count: all.length, totalMin: all.reduce((s, b) => s + b.durationMin, 0), totalEur: all.filter(b => b.status !== 'cancelled').reduce((s, b) => s + b.priceEur, 0), confirmed: all.filter(b => b.status === 'confirmed' || b.status === 'in_progress').length, cancelled: all.filter(b => b.status === 'cancelled').length };
  }
  get weekStats() { return { count: this.mockBookings().length, confirmed: this.mockBookings().filter(b => b.status === 'confirmed' || b.status === 'in_progress').length, inProgress: this.mockBookings().filter(b => b.status === 'in_progress').length, completed: this.mockBookings().filter(b => b.status === 'completed').length, noShow: this.mockBookings().filter(b => b.status === 'no_show').length }; }
  get allServices() { return [{ id: 'nega-obraza', name: 'Nega obraza (45 min, 35€)' }, { id: 'maska-obraza', name: 'Maska obraza (30 min, 25€)' }, { id: 'ciscenje-obraza', name: 'Čiščenje obraza (60 min, 50€)' }]; }
  timeSlots = ['09:00','09:30','10:00','10:30','11:00','11:30','12:00','13:00','13:30','14:00','14:30','15:00','15:30','16:00','16:30','17:00','17:30'];
  get freeSlots() { const taken = this.todaysBookings.map(b => b.bookingTime); return this.timeSlots.filter(t => !taken.includes(t) && t !== '12:00'); }

  getBookingAt(time: string) { return this.todaysBookings.find(b => b.bookingTime === time); }
  statusLabel(s: string) { const m: any = { confirmed: 'Potrjeno', in_progress: 'V teku', completed: 'Končano', no_show: 'Ni prišel/-a', cancelled: 'Odpovedano' }; return m[s] || s; }
  statusPillClass(s: string) { const m: any = { confirmed: '', in_progress: 'warn', completed: 'success', no_show: 'dark', cancelled: 'dark' }; return m[s] || 'dark'; }
  bookingDot(s: string) { const m: any = { confirmed: '●', in_progress: '◉', completed: '○', no_show: '✕', cancelled: '—' }; return m[s] || '●'; }

  selectBooking(b: any) { this.selectedBooking = this.selectedBooking?.id === b.id ? null : b; }
  weekDays() { const [y,m,day] = this.bookingDate().split('-').map(Number); const d = new Date(Date.UTC(y, m-1, day)); const dow = d.getUTCDay(); const mon = new Date(Date.UTC(y, m-1, day - (dow === 0 ? 6 : dow - 1))); return Array.from({ length: 6 }, (_, i) => { const dt = new Date(mon); dt.setUTCDate(mon.getUTCDate() + i); return dt.toISOString().slice(0, 10); }); }
  weekDayLabel(d: string) { const [y,m,day] = d.split('-').map(Number); const dt = new Date(Date.UTC(y, m-1, day)); const n = ['PO','TO','SR','ČE','PE','SO'][dt.getUTCDay() - 1] || '??'; return n + ' ' + String(day) + '.'; }
  getWeekBooking(date: string, time: string) { return this.mockBookings().find(b => b.bookingDate === date && b.bookingTime === time); }

  addDays(dateStr: string, n: number) { const [y,m,d] = dateStr.split('-').map(Number); const dt = new Date(Date.UTC(y, m-1, d + n)); return dt.toISOString().slice(0, 10); }
  prevDay() { this.bookingDate.set(this.addDays(this.bookingDate(), -1)); this.selectedBooking = null; }
  nextDay() { this.bookingDate.set(this.addDays(this.bookingDate(), 1)); this.selectedBooking = null; }
  goToday() { this.bookingDate.set(new Date().toISOString().slice(0, 10)); this.selectedBooking = null; }
  toggleBookingView() { this.bookingView.set(this.bookingView() === 'day' ? 'week' : 'day'); }
  todayStr() { return new Date().toISOString().slice(0, 10); }

  get visibleCount() { return this.leads().length; }
  get leadCount() { return this.allLeads().length; }
  get takeoverCount() { return this.allLeads().filter(l => l.takeoverActive).length; }
  get contactCount() { return this.allLeads().filter(l => l.phone || l.email).length; }
  get surveyCount() { return this.allLeads().filter(l => l.status === 'SURVEY').length; }
  get openChatCount() { return this.allLeads().filter(l => l.status === 'OPEN_CHAT').length; }
  get humanCount() { return this.allLeads().filter(l => l.status === 'HUMAN_TAKEOVER').length; }
}
