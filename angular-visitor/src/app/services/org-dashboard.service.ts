import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class OrgDashboardService {
  constructor(private http: HttpClient) {}

  getOrgs() { return this.http.get<any[]>('/api/admin/organizations'); }
  getLeads(orgId: number) { return this.http.get<any[]>('/api/organizations/' + orgId + '/leads'); }
  getMessages(orgId: number, sid: string) { return this.http.get<any[]>('/api/organizations/' + orgId + '/leads/' + sid + '/messages'); }
  sendTakeover(orgId: number, sid: string, text: string) {
    return this.http.post('/chat/staff', { orgId, sid, text });
  }
  endTakeover(orgId: number, sid: string) {
    return this.http.post('/api/organizations/' + orgId + '/leads/' + sid + '/takeover/end', {});
  }
  deleteLead(orgId: number, sid: string) {
    return this.http.delete('/api/organizations/' + orgId + '/leads/' + sid);
  }
}
