import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable, throwError, timer, of } from 'rxjs';
import { catchError, retryWhen, delayWhen, scan, switchMap, timeout } from 'rxjs/operators';
import { environment, getTenantSlug } from '../../environments/environment';

// --- Request / Response types mirroring Java backend ---

export interface ChatRequest {
  sid?: string;
  message: string;
  tenant_slug: string;
  meta?: Record<string, unknown>;
}

export interface ChatResponse {
  sid: string;
  reply: string;
  chatMode: string;
  storyComplete: boolean;
  surveyProgress: number;
  currentStep: SurveyStep | null;
  completionTitle: string | null;
  completionSubtitle: string | null;
}

export interface SurveyStep {
  orderIndex: number;
  questionType: string;
  title: string;
  description: string;
  placeholder: string;
  options: string[];
}

export interface QualifierActiveResponse {
  active: boolean;
  qualifierName?: string;
}

export interface MessageResponse {
  role: string;
  text: string;
  timestamp: number;
}

export interface PollEvent {
  _seq: number;
  type: string;
  [key: string]: unknown;
}

export interface PollResult {
  ok: boolean;
  events: PollEvent[];
  next: number;
}

// --- Service ---

@Injectable({ providedIn: 'root' })
export class ChatApiService {
  private readonly baseUrl = environment.apiUrl;
  private get tenantSlug(): string {
    return getTenantSlug();
  }

  constructor(private readonly http: HttpClient) {}

  /**
   * Send a message and receive the reply as a stream of tokens.
   * Returns an Observable that emits each token string, then completes.
   */
  sendMessageStream(sid: string | undefined, message: string): Observable<string> {
    const body: ChatRequest = {
      sid,
      message,
      tenant_slug: this.tenantSlug,
    };

    return new Observable<string>((observer) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);

      fetch(`${this.baseUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok) {
            clearTimeout(timeout);
            observer.error(new ApiError('sendMessageStream', `HTTP ${response.status}`, response.status));
            return;
          }
          const reader = response.body?.getReader();
          if (!reader) {
            clearTimeout(timeout);
            observer.error(new ApiError('sendMessageStream', 'No response body', 0));
            return;
          }
          const decoder = new TextDecoder();
          let buffer = '';
          let finalSid = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.token) {
                    observer.next(data.token);
                  }
                  if (data.sid) {
                    finalSid = data.sid;
                  }
                  if (data.done && finalSid) {
                    observer.next('__SID__:' + finalSid);
                  }
                  if (data.profile) {
                    observer.next('__PROFILE__:' + JSON.stringify(data.profile));
                  }
                } catch { /* skip malformed */ }
              }
            }
          }
          clearTimeout(timeout);
          observer.complete();
        })
        .catch((err) => {
          clearTimeout(timeout);
          observer.error(new ApiError('sendMessageStream', err.message || 'Network error', 0));
        });

      return () => {
        clearTimeout(timeout);
        controller.abort();
      };
    });
  }

  /**
   * Send a message to the AI receptionist (non-streaming fallback).
   * Retries up to environment.retryCount times with exponential backoff on 5xx errors.
   */
  sendMessage(sid: string | undefined, message: string): Observable<ChatResponse> {
    const body: ChatRequest = {
      sid,
      message,
      tenant_slug: this.tenantSlug,
    };

    return this.http.post<ChatResponse>(`${this.baseUrl}/chat`, body).pipe(
      timeout(30000), // 30s timeout
      retryWithBackoff(environment.retryCount, environment.retryDelayMs),
      catchError((err) => this.handleError('sendMessage', err)),
    );
  }

  /**
   * Check if organization has an active qualifier (AI receptionist mode).
   */
  getQualifierActive(): Observable<QualifierActiveResponse> {
    return this.http
      .get<QualifierActiveResponse>(
        `${this.baseUrl}/api/public/organizations/${this.tenantSlug}/qualifier-active`,
      )
      .pipe(
        timeout(10000),
        retryWithBackoff(2, 500),
        catchError((err) => this.handleError('getQualifierActive', err)),
      );
  }

  /**
   * Fetch the conversation thread (message history).
   */
  getThread(sid: string): Observable<MessageResponse[]> {
    return this.http
      .get<MessageResponse[]>(
        `${this.baseUrl}/api/public/organizations/${this.tenantSlug}/leads/${sid}/messages`,
      )
      .pipe(
        timeout(10000),
        retryWithBackoff(2, 500),
        catchError((err) => this.handleError('getThread', err)),
      );
  }

  /**
   * Get LiveKit session info for visitor (token, room, wsUrl).
   */
  getLiveSession(sid: string): Observable<{sid: string; status: string; managerDisplayName: string; roomName: string; wsUrl: string; token: string}> {
    return this.http
      .get<any>(`${this.baseUrl}/api/public/organizations/${this.tenantSlug}/live-session`, {
        params: new HttpParams().set('sid', sid),
      })
      .pipe(
        timeout(10000),
        catchError((err) => this.handleError('getLiveSession', err)),
      );
  }

  /**
   * Poll for real-time events (takeover, staff join, etc.).
   */
  pollEvents(sid: string, since: number): Observable<PollResult> {
    const params = new HttpParams()
      .set('sid', sid)
      .set('since', String(since))
      .set('timeout', String(environment.pollingTimeout))
      .set('limit', '50')
      .set('tenantSlug', this.tenantSlug);

    return this.http
      .get<PollResult>(`${this.baseUrl}/chat-events/poll`, { params })
      .pipe(
        timeout((environment.pollingTimeout + 5) * 1000),
        catchError((err) => {
          // Poll timeouts are expected — don't treat as error
          if (err instanceof HttpErrorResponse && err.status === 0) {
            return of({ ok: true, events: [], next: since });
          }
          console.warn('[ChatApi] Poll error, continuing:', err.message);
          return of({ ok: true, events: [], next: since });
        }),
      );
  }

  // --- Error handling ---

  private handleError(context: string, error: unknown): Observable<never> {
    if (error instanceof HttpErrorResponse) {
      const msg = `[ChatApi] ${context} failed — HTTP ${error.status}: ${error.message}`;
      console.error(msg);

      if (error.status === 404) {
        return throwError(() => new ApiError(context, 'Organization or resource not found. Is the Java backend running?', error.status));
      }
      if (error.status === 0 || error.status >= 500) {
        return throwError(() => new ApiError(context, 'Backend unavailable. Please ensure the Java server is running on port 8080.', error.status));
      }
      return throwError(() => new ApiError(context, error.message || 'Unknown error', error.status));
    }

    if (error instanceof Error && error.name === 'TimeoutError') {
      console.error(`[ChatApi] ${context} timed out`);
      return throwError(() => new ApiError(context, 'Request timed out. The backend may be slow or unreachable.', 0));
    }

    console.error(`[ChatApi] ${context} unexpected error:`, error);
    return throwError(() => new ApiError(context, 'An unexpected error occurred.', 0));
  }
}

/**
 * Retry operator with exponential backoff.
 * Retries on network errors (status 0) and server errors (5xx).
 */
function retryWithBackoff<T>(maxRetries: number, initialDelayMs: number) {
  return retryWhen<T>((errors: Observable<unknown>) =>
    errors.pipe(
      scan((retryCount, error) => {
        if (retryCount >= maxRetries) throw error;
        if (error instanceof HttpErrorResponse && error.status !== 0 && error.status < 500) {
          throw error; // don't retry 4xx
        }
        return retryCount + 1;
      }, 0),
      delayWhen((retryCount) => {
        const delay = initialDelayMs * Math.pow(2, (retryCount as number) - 1);
        console.warn(`[ChatApi] Retry ${retryCount}/${maxRetries} in ${delay}ms...`);
        return timer(delay);
      }),
    ),
  );
}

export class ApiError extends Error {
  constructor(
    public readonly context: string,
    message: string,
    public readonly httpStatus: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
