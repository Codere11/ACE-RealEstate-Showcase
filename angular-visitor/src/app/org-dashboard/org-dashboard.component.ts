import { Component, signal, OnInit, OnDestroy, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

@Component({
  standalone: true,
  imports: [FormsModule],
  templateUrl: './org-dashboard.component.html',
  styleUrl: './org-dashboard.component.scss',
})
export class OrgDashboardComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  slug = signal(''); orgId = 0; error = signal('');
  leads = signal<any[]>([]); allLeads = signal<any[]>([]);
  messages = signal<any[]>([]);
  selectedSid = ''; takeoverActive = signal(false); takeoverText = '';
  activeTab = 'leads';
  filters = { search: '', interest: 'all', status: 'all', minProgress: 0, takeoverOnly: false };
  private timer: any;

  async ngOnInit() {
    this.slug.set(this.route.snapshot.paramMap.get('slug') || '');
    await this.resolveOrg();
    if (this.orgId) { await this.loadLeads(); this.timer = setInterval(() => this.loadLeads(), 10000); }
  }
  ngOnDestroy() { if (this.timer) clearInterval(this.timer); }

  private async resolveOrg() {
    try {
      const r = await fetch('/api/admin/organizations', { credentials: 'same-origin' });
      if (r.status === 401) { window.location.href = '/login'; return; }
      const org = (await r.json()).find((o: any) => o.slug === this.slug());
      if (!org) { this.error.set('Organizacija ne obstaja.'); return; }
      this.orgId = org.id;
    } catch(e) { console.error('resolveOrg failed', e); this.error.set('Napaka pri povezavi.'); }
  }

  async loadLeads() {
    if (!this.orgId) return;
    try {
      const r = await fetch('/api/organizations/' + this.orgId + '/leads', { credentials: 'same-origin' });
      if (r.ok) {
        let list = await r.json();
        list.sort((a:any,b:any) => (b.staffRequested ? 1 : 0) - (a.staffRequested ? 1 : 0) || (b.lastSeenSec||0) - (a.lastSeenSec||0));
        this.allLeads.set(list); this.applyFilters();
      }
    } catch(e) { console.error('loadLeads failed', e); }
  }

  applyFilters() {
    let list = this.allLeads();
    const q = this.filters.search.toLowerCase();
    if (q) list = list.filter(l => (l.name||'').toLowerCase().includes(q) || (l.sid||'').toLowerCase().includes(q));
    if (this.filters.interest !== 'all') list = list.filter(l => (l.interest||'') === this.filters.interest);
    if (this.filters.status !== 'all') list = list.filter(l => l.status === this.filters.status);
    if (this.filters.minProgress > 0) list = list.filter(l => (l.surveyProgress||0) >= this.filters.minProgress);
    if (this.filters.takeoverOnly) list = list.filter(l => l.takeoverActive);
    this.leads.set(list);
  }

  async select(sid: string) {
    this.selectedSid = sid;
    const lead = this.allLeads().find(l => l.sid === sid);
    this.takeoverActive.set(lead?.takeoverActive || false);
    try {
      const r = await fetch('/api/organizations/' + this.orgId + '/leads/' + sid + '/messages', { credentials: 'same-origin' });
      if (r.ok) this.messages.set(await r.json());
    } catch {}
  }

  async sendTakeover() {
    if (!this.selectedSid || !this.takeoverText.trim()) return;
    try {
      const r = await fetch('/chat/staff', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orgId: this.orgId, sid: this.selectedSid, text: this.takeoverText })
      });
      if (r.ok) { this.takeoverText = ''; this.takeoverActive.set(true); await this.loadLeads(); await this.select(this.selectedSid); }
    } catch {}
  }

  async endTakeover() {
    if (!this.selectedSid) return;
    try {
      await fetch('/api/organizations/' + this.orgId + '/leads/' + this.selectedSid + '/takeover/end', { method: 'POST', credentials: 'same-origin' });
      this.takeoverActive.set(false); await this.loadLeads(); await this.select(this.selectedSid);
    } catch {}
  }

  async deleteSelected() {
    if (!this.selectedSid || !confirm('Delete this lead?')) return;
    await this.deleteLead(this.selectedSid);
  }

  async deleteLead(sid: string) {
    if (!confirm('Delete this lead?')) return;
    try {
      await fetch('/api/organizations/' + this.orgId + '/leads/' + sid, { method: 'DELETE', credentials: 'same-origin' });
      if (sid === this.selectedSid) { this.selectedSid = ''; this.messages.set([]); this.takeoverActive.set(false); }
      await this.loadLeads();
    } catch {}
  }

  selectedLeadName() { return this.allLeads().find(l => l.sid === this.selectedSid)?.name || 'Visitor'; }
  get visibleCount() { return this.leads().length; }
  get leadCount() { return this.allLeads().length; }
  get takeoverCount() { return this.allLeads().filter(l => l.takeoverActive).length; }
  get contactCount() { return this.allLeads().filter(l => l.phone || l.email).length; }
  get surveyCount() { return this.allLeads().filter(l => l.status === 'SURVEY').length; }
  get openChatCount() { return this.allLeads().filter(l => l.status === 'OPEN_CHAT').length; }
  get humanCount() { return this.allLeads().filter(l => l.status === 'HUMAN_TAKEOVER').length; }
}
