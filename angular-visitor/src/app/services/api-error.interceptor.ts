import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

/**
 * Global HTTP error interceptor.
 * Logs all errors and normalizes them for the UI layer.
 */
export const apiErrorInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        // Network error (backend down / CORS / no connection)
        if (error.status === 0) {
          console.error(
            `[API] Network error — ${req.method} ${req.url}. Is the backend running?`,
          );
        } else {
          console.error(
            `[API] HTTP ${error.status} — ${req.method} ${req.url}: ${error.message}`,
          );
        }
      } else {
        console.error(`[API] Unexpected error — ${req.method} ${req.url}:`, error);
      }
      return throwError(() => error);
    }),
  );
};
