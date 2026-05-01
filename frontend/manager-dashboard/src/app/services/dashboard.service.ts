import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { AuthService } from './auth.service';

// Types
export type OrganizationPaymentSettings = {
  id: number;
  organization_id: number;
  provider: 'stripe';
  mode: 'stripe_connect_standard';
  payments_enabled: boolean;
  default_currency: string;
  stripe_account_id?: string | null;
  stripe_connect_status: 'not_connected' | 'pending' | 'connected' | 'restricted' | 'error';
  stripe_onboarding_complete: boolean;
  stripe_details_submitted: boolean;
  stripe_charges_enabled: boolean;
  stripe_payouts_enabled: boolean;
  stripe_publishable_key?: string | null;
  stripe_scope?: string | null;
  stripe_livemode: boolean;
  stripe_last_error?: string | null;
  last_synced_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type PaymentRequest = {
  id: number;
  organization_id: number;
  sid: string;
  created_by_user_id?: number | null;
  provider: string;
  provider_payment_id?: string | null;
  provider_session_id?: string | null;
  public_token: string;
  amount_cents: number;
  currency: string;
  purpose: string;
  note: string;
  status: 'draft' | 'sent' | 'paid' | 'failed' | 'expired' | 'cancelled';
  payment_url: string;
  expires_at?: string | null;
  paid_at?: string | null;
  provider_payload?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
};

export type LeadProfile = {
  id: number;
  organization_id: number;
  sid: string;
  qualifier_id?: number | null;
  qualifier_version: number;
  profile?: Record<string, any> | null;
  field_confidence?: Record<string, number> | null;
  qualification_score: number;
  qualification_band: 'hot' | 'warm' | 'cold';
  confidence_overall: number;
  reasoning: string;
  recommended_next_action: string;
  missing_fields?: string[] | null;
  takeover_eligible: boolean;
  video_offer_eligible: boolean;
  last_qualified_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type Lead = {
  id: string;
  name: string;
  industry: string;
  score: number;
  stage: string;
  compatibility: boolean;
  interest: 'High' | 'Medium' | 'Low';
  /** NEW: actual strings coming from backend (may be empty). */
  phoneText?: string;
  emailText?: string;
  /** Back-compat flags for UI conditions. */
  phone: boolean;
  email: boolean;
  adsExp: boolean;
  lastMessage: string;
  lastSeenSec: number;
  notes: string;
  
  // Survey fields
  survey_started_at?: string | null;
  survey_completed_at?: string | null;
  survey_answers?: Record<string, any> | null;
  survey_progress?: number;

  // AI qualifier fields
  qualification_band?: 'hot' | 'warm' | 'cold';
  qualification_confidence?: number;
  qualification_reasoning?: string;
  recommended_next_action?: string;
  takeover_eligible?: boolean;
  video_offer_eligible?: boolean;
  qualifier_profile?: Record<string, any> | null;
  qualifier_missing_fields?: string[] | null;
};

export type KPIs = {
  visitors: number;
  interactions: number;
  contacts: number;
  avgResponseSec: number;
  activeLeads: number;
};

export type Funnel = {
  awareness: number;
  interest: number;
  meeting: number;
  close: number;
};

export type ChatLog = {
  sid: string;
  role: 'user' | 'assistant' | 'staff';
  text: string;
  timestamp: number;
};

@Injectable({
  providedIn: 'root'
})
export class DashboardService {
  private baseUrl = 'http://127.0.0.1:8000';

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getOrgId(): number {
    return this.authService.getCurrentUser()?.organization_id || 1;
  }

  getLeads(): Observable<Lead[]> {
    return this.http.get<Lead[]>(`${this.baseUrl}/leads/`).pipe(
      map(list =>
        list.map(l => ({
          ...l,
          // ensure booleans exist even if backend only sends strings
          phone: !!(l as any).phone || !!l.phoneText,
          email: !!(l as any).email || !!l.emailText,
        }))
      )
    );
  }

  getKPIs(): Observable<KPIs> {
    return this.http.get<KPIs>(`${this.baseUrl}/kpis/`);
  }

  getFunnel(): Observable<Funnel> {
    return this.http.get<Funnel>(`${this.baseUrl}/funnel/`);
  }

  getObjections(): Observable<string[]> {
    return this.http.get<string[]>(`${this.baseUrl}/objections/`);
  }

  /** All chats (flat) */
  getChats(): Observable<ChatLog[]> {
    return this.http.get<ChatLog[]>(`${this.baseUrl}/chats/`);
  }

  /** Chats for a specific lead/session id (persistent-first) */
  getChatsForLead(sid: string): Observable<ChatLog[]> {
    return this.http.get<ChatLog[]>(`${this.baseUrl}/chats?sid=${encodeURIComponent(sid)}`);
  }

  /** Send a STAFF message (dashboard takeover) -> persisted as role=staff */
  sendStaffMessage(sid: string, text: string): Observable<{ ok: boolean; message?: ChatLog }> {
    return this.http.post<{ ok: boolean; message?: ChatLog }>(`${this.baseUrl}/chat/staff`, { sid, text });
  }

  getLeadProfiles(): Observable<LeadProfile[]> {
    const orgId = this.getOrgId();
    return this.http.get<LeadProfile[]>(`${this.baseUrl}/api/organizations/${orgId}/qualifiers/lead-profiles`);
  }

  getPaymentSettings(): Observable<OrganizationPaymentSettings> {
    const orgId = this.getOrgId();
    return this.http.get<OrganizationPaymentSettings>(`${this.baseUrl}/api/organizations/${orgId}/payment-settings`);
  }

  startStripeConnect(): Observable<{ url: string }> {
    const orgId = this.getOrgId();
    return this.http.post<{ url: string }>(`${this.baseUrl}/api/organizations/${orgId}/payment-settings/stripe/connect`, {});
  }

  refreshStripeConnect(): Observable<OrganizationPaymentSettings> {
    const orgId = this.getOrgId();
    return this.http.post<OrganizationPaymentSettings>(`${this.baseUrl}/api/organizations/${orgId}/payment-settings/stripe/refresh`, {});
  }

  getPaymentRequests(sid?: string): Observable<PaymentRequest[]> {
    const orgId = this.getOrgId();
    const query = sid ? `?sid=${encodeURIComponent(sid)}` : '';
    return this.http.get<PaymentRequest[]>(`${this.baseUrl}/api/organizations/${orgId}/payment-requests${query}`);
  }

  createPaymentRequest(payload: { sid: string; amount: number; currency: string; purpose: string; note?: string; expires_in_hours?: number; }): Observable<PaymentRequest> {
    const orgId = this.getOrgId();
    return this.http.post<PaymentRequest>(`${this.baseUrl}/api/organizations/${orgId}/payment-requests`, payload);
  }

  /** Delete a lead by ID */
  deleteLead(leadId: string): Observable<{ success: boolean; message: string }> {
    return this.http.delete<{ success: boolean; message: string }>(`${this.baseUrl}/leads/${leadId}`);
  }

  /** Get survey flow for score calculation */
  getSurveyFlow(orgSlug: string, surveySlug: string): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/s/${orgSlug}/${surveySlug}`);
  }
}
