export const environment = {
  production: false,
  apiUrl: '',  // empty = same origin in prod, or proxied in dev
  get tenantSlug(): string {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      return params.get('org') || 'demo';
    }
    return 'demo';
  },
  pollingIntervalMs: 5000,
  pollingTimeout: 20,
  retryCount: 3,
  retryDelayMs: 1000,
};
