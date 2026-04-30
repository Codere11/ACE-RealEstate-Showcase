import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { Qualifier, QualifierCreate, QualifierUpdate } from '../models/qualifier.model';

@Injectable({
  providedIn: 'root'
})
export class QualifiersService {
  private apiUrl = 'http://localhost:8000/api/organizations';

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getOrgId(): number {
    return this.authService.getCurrentUser()?.organization_id || 1;
  }

  listQualifiers(status?: string): Observable<Qualifier[]> {
    const options = status ? { params: { status } } : {};
    return this.http.get<Qualifier[]>(`${this.apiUrl}/${this.getOrgId()}/qualifiers`, options);
  }

  getQualifier(qualifierId: number): Observable<Qualifier> {
    return this.http.get<Qualifier>(`${this.apiUrl}/${this.getOrgId()}/qualifiers/${qualifierId}`);
  }

  getActiveQualifier(): Observable<Qualifier> {
    return this.http.get<Qualifier>(`${this.apiUrl}/${this.getOrgId()}/qualifiers/active`);
  }

  createQualifier(payload: QualifierCreate): Observable<Qualifier> {
    return this.http.post<Qualifier>(`${this.apiUrl}/${this.getOrgId()}/qualifiers`, payload);
  }

  updateQualifier(qualifierId: number, payload: QualifierUpdate): Observable<Qualifier> {
    return this.http.put<Qualifier>(`${this.apiUrl}/${this.getOrgId()}/qualifiers/${qualifierId}`, payload);
  }

  publishQualifier(qualifierId: number): Observable<Qualifier> {
    return this.http.post<Qualifier>(`${this.apiUrl}/${this.getOrgId()}/qualifiers/${qualifierId}/publish`, {});
  }

  archiveQualifier(qualifierId: number): Observable<Qualifier> {
    return this.http.post<Qualifier>(`${this.apiUrl}/${this.getOrgId()}/qualifiers/${qualifierId}/archive`, {});
  }
}
