export const environment = {
  production: false,
  apiUrl: '',  // proxied via proxy.conf.json
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
