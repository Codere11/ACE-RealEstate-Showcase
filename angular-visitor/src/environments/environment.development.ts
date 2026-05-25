export const environment = {
  production: false,
  apiUrl: '',
  defaultTenantSlug: 'demo',
  pollingIntervalMs: 1000,
  pollingTimeout: 1,
  retryCount: 3,
  retryDelayMs: 1000,
};

export function getTenantSlug(): string {
  if (typeof window !== 'undefined') {
    // 1. Explicit ?org= query param takes priority
    const params = new URLSearchParams(window.location.search);
    const org = params.get('org');
    if (org) return org;
    // 2. Extract first segment from URL path: /some-org/page → some-org
    const segments = window.location.pathname.replace(/^\/+/, '').split('/');
    const firstSegment = segments[0];
    if (firstSegment && firstSegment !== 'demo') return firstSegment;
  }
  return environment.defaultTenantSlug;
}
