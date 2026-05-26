import { Component, signal, OnInit, OnDestroy, inject, ElementRef, ViewChild, NgZone } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { OrgDashboardService } from '../services/org-dashboard.service';
import { firstValueFrom } from 'rxjs';
import { Room, RoomEvent, LocalVideoTrack, RemoteParticipant, RemoteTrack, RemoteTrackPublication, Track, createLocalVideoTrack } from 'livekit-client';

@Component({
  standalone: true,
  imports: [FormsModule],
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
  get visibleCount() { return this.leads().length; }
  get leadCount() { return this.allLeads().length; }
  get takeoverCount() { return this.allLeads().filter(l => l.takeoverActive).length; }
  get contactCount() { return this.allLeads().filter(l => l.phone || l.email).length; }
  get surveyCount() { return this.allLeads().filter(l => l.status === 'SURVEY').length; }
  get openChatCount() { return this.allLeads().filter(l => l.status === 'OPEN_CHAT').length; }
  get humanCount() { return this.allLeads().filter(l => l.status === 'HUMAN_TAKEOVER').length; }
}
