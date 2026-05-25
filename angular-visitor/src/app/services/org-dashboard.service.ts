import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class OrgDashboardService {
  constructor(private http: HttpClient) {}

  getLeads(orgId: number): Observable<any[]> {
    return this.http.get<any[]>('/api/organizations/' + orgId + '/leads', { withCredentials: true }).pipe(
      catchError(e => { if (e.status === 401) window.location.href = '/login'; return throwError(() => e); })
    );
  }

  getMessages(orgId: number, sid: string): Observable<any[]> {
    return this.http.get<any[]>('/api/organizations/' + orgId + '/leads/' + sid + '/messages', { withCredentials: true });
  }

  sendTakeover(orgId: number, sid: string, text: string): Observable<any> {
    return this.http.post('/chat/staff', { orgId, sid, text }, { withCredentials: true });
  }

  endTakeover(orgId: number, sid: string): Observable<any> {
    return this.http.post('/api/organizations/' + orgId + '/leads/' + sid + '/takeover/end', {}, { withCredentials: true });
  }

  deleteLead(orgId: number, sid: string): Observable<any> {
    return this.http.delete('/api/organizations/' + orgId + '/leads/' + sid, { withCredentials: true });
  }
}
