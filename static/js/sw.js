/*
 * static/js/sw.js — The service worker.
 *
 * PRD §8: a session must not die because the wifi dropped between Look and
 * Smell. The client state machine already keeps the *data* safe — every tap
 * is in IndexedDB before anything is sent. This closes the other half: making
 * sure the page, its stylesheet and its scripts are still there when the
 * taster reloads or comes back tomorrow in a cellar.
 *
 * Two strategies, split by what the thing is:
 *
 *   Static assets (hashed or versioned URLs) — cache-first. They never change
 *   under a given URL, so a network trip for them is pure latency.
 *
 *   Pages — network-first, falling back to cache, falling back to the offline
 *   page. A page is a live thing; serving a stale journal to someone who has
 *   a network would be wrong.
 *
 * API responses are deliberately NOT cached. The lexicon is already cached in
 * IndexedDB by session_db, where the app can reason about it; a second copy
 * here with different eviction rules would be a bug waiting to happen. And a
 * cached POST would be actively harmful.
 *
 * CACHE_VERSION is substituted at serve time from the release version, so a
 * deploy invalidates the shell without anyone having to remember to bump a
 * constant.
 */

const CACHE_VERSION = '__CACHE_VERSION__';
const CACHE_NAME = `wineguide-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline/';

/*
 * Substituted from settings.DEBUG. In development the cache version is the
 * constant "dev", so it never changes, and cache-first on /static/ means an
 * edited module is never fetched again — you change a file, reload, and see
 * the old one, with nothing on screen to say why. Rather than ask every
 * developer to learn that, the worker stands down entirely when DEBUG is on.
 *
 * The offline behaviour this disables is covered by the Playwright suite,
 * which runs against DEBUG=True — so those tests drive the real worker by
 * pointing at it directly rather than relying on this path.
 */
const DEV = __DEV__;

/** The shell: enough to run a tasting with no network at all. */
const PRECACHE = ['/taste/', '/offline/'];

self.addEventListener('install', (event) => {
  if (DEV) return;
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE))
      // A precache miss (one URL 404s, or the network died mid-install) must
      // not abort the install — a worker that fails to install leaves the
      // client with no worker at all, which is strictly worse than one with a
      // partial cache.
      .catch(() => undefined),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith('wineguide-') && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

/**
 * Whether a request should be served from cache first.
 *
 * @param {URL} url
 * @returns {boolean}
 */
function isStatic(url) {
  return url.pathname.startsWith('/static/');
}

/**
 * Whether a request should never touch the cache.
 *
 * @param {URL} url
 * @returns {boolean}
 */
function isApi(url) {
  return url.pathname.startsWith('/api/');
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  // Only GET. A cached POST would replay a mutation; the offline queue in
  // session_sync is what handles writes, and it does so with intent.
  if (request.method !== 'GET') return;

  if (DEV) return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isApi(url)) return;

  if (isStatic(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
  }
});

/**
 * Serve from cache, falling back to the network and filling the cache.
 *
 * @param {Request} request
 * @returns {Promise<Response>}
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, response.clone());
  }
  return response;
}

/**
 * Serve from the network, falling back to cache and then the offline page.
 *
 * @param {Request} request
 * @returns {Promise<Response>}
 */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (e) {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offline = await caches.match(OFFLINE_URL);
    if (offline) return offline;
    return new Response('Offline', { status: 503, statusText: 'Offline' });
  }
}
