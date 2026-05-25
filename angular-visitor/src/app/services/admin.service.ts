import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AdminService {
  constructor(private http: HttpClient) {}

  getOrgs(): Observable<any[]> {
    return this.http.get<any[]>('/api/admin/organizations', { withCredentials: true }).pipe(
      catchError(e => { if (e.status === 401) window.location.href = '/login'; return throwError(() => e); })
    );
  }

  createOrg(name: string, slug: string): Observable<any> {
    return this.http.post('/api/admin/organizations', { name, slug, active: 'true' }, { withCredentials: true });
  }

  getUsers(): Observable<any[]> {
    return this.http.get<any[]>('/api/admin/users', { withCredentials: true }).pipe(
      catchError(e => { if (e.status === 401) window.location.href = '/login'; return throwError(() => e); })
    );
  }

  createUser(username: string, email: string, password: string, role: string, orgId?: number): Observable<any> {
    return this.http.post('/api/admin/users', { username, email, password, role, organizationId: orgId }, { withCredentials: true });
  }
}
