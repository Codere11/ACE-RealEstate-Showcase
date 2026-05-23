export const environment = {
  production: false,
  apiUrl: '',  // empty = same origin in prod, or proxied in dev
  tenantSlug: 'demo',
  pollingIntervalMs: 5000,
  pollingTimeout: 20,
  retryCount: 3,
  retryDelayMs: 1000,
};
