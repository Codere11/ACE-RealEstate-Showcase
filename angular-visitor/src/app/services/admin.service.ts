import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class AdminService {
  constructor(private http: HttpClient) {}

  getOrgs() { return this.http.get<any[]>('/api/admin/organizations'); }
  createOrg(name: string, slug: string) { return this.http.post('/api/admin/organizations', { name, slug, active: 'true' }); }
  getUsers() { return this.http.get<any[]>('/api/admin/users'); }
  createUser(username: string, email: string, password: string, role: string, orgId?: number) {
    return this.http.post('/api/admin/users', { username, email, password, role, organizationId: orgId });
  }
}
