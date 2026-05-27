import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

export const apiErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('ace_token');
  if (token) {
    req = req.clone({ setHeaders: { Authorization: 'Bearer ' + token } });
  }
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        sessionStorage.setItem('ace_return_url', window.location.pathname + window.location.search);
        window.location.href = '/login';
      }
      return throwError(() => error);
    }),
  );
};
