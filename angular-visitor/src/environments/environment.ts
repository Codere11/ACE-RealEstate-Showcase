export const environment = {
  production: false,
  apiUrl: '',  // empty = same origin in prod, or proxied in dev
  defaultTenantSlug: 'demo',
  pollingIntervalMs: 5000,
  pollingTimeout: 20,
  retryCount: 3,
  retryDelayMs: 1000,
};

export function getTenantSlug(): string {
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const org = params.get('org');
    if (org) return org;
  }
  return environment.defaultTenantSlug;
}
