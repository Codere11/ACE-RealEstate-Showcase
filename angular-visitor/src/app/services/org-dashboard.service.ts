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
  goLive(orgId: number, sid: string) {
    return this.http.post<any>('/api/organizations/' + orgId + '/live-sessions/go-live', { sid });
  }
  endLive(orgId: number, sid: string) {
    return this.http.post<any>('/api/organizations/' + orgId + '/live-sessions/end', { sid });
  }
  deleteLead(orgId: number, sid: string) {
    return this.http.delete('/api/organizations/' + orgId + '/leads/' + sid);
  }
  getBookings(orgId: number, dateFrom?: string, dateTo?: string) {
    let params: any = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    return this.http.get<any[]>('/api/organizations/' + orgId + '/bookings', { params });
  }
  createBooking(orgId: number, data: any) {
    return this.http.post<any>('/api/organizations/' + orgId + '/bookings', data);
  }
  deleteBooking(orgId: number, bookingId: number) {
    return this.http.delete('/api/organizations/' + orgId + '/bookings/' + bookingId);
  }
  analize(orgId: number) {
    return this.http.post<any>('/api/organizations/' + orgId + '/analize', {});
  }
  labelLead(orgId: number, sid: string, messages: any[]) {
    return this.http.post<any>('/api/organizations/' + orgId + '/analize/label', { sid, messages });
  }
  personaChat(orgId: number, personaId: string, message: string, leads: any[], history: any[]) {
    return this.http.post<any>('/api/organizations/' + orgId + '/analize/chat', { persona_id: personaId, message, leads, history });
  }

  saveMeetingNotes(orgId: number, sid: string, notes: string) {
    return this.http.post<any>('/api/organizations/' + orgId + '/leads/' + sid + '/meeting-notes', { notes });
  }
}
