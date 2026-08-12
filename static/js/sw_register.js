/*
 * static/js/sw_register.js — Registering the service worker.
 *
 * Deliberately tiny and deliberately silent. Registration failing is not
 * something the taster can act on, and a console full of red on an
 * unsupported browser is noise for whoever is debugging something real.
 *
 * Registered at '/' scope, which is why the worker is served from a view at
 * the site root rather than out of /static/ — see apps/core/views.py.
 */

export function registerServiceWorker(navigatorRef = navigator) {
  if (!('serviceWorker' in navigatorRef)) return Promise.resolve(null);
  return navigatorRef.serviceWorker
    .register('/sw.js', { scope: '/' })
    .catch(() => null);
}

if (typeof navigator !== 'undefined' && typeof window !== 'undefined') {
  // After load: registration competes with the page's own requests for
  // bandwidth, and the first visit should render before it starts caching for
  // the second.
  window.addEventListener('load', () => registerServiceWorker());
}
