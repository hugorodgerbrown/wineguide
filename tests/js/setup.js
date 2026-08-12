/*
 * tests/js/setup.js — Vitest global setup, registered via vitest.config.mjs's
 * `setupFiles`. Runs once per test file, before that file's module graph is
 * imported.
 *
 * `fake-indexeddb/auto` installs an in-memory IndexedDB on globalThis. jsdom
 * does not ship one (https://github.com/jsdom/jsdom/issues/2306), and it is
 * exactly the surface session_db.js is built on — the store that makes a
 * tasting survive a dropped connection.
 *
 * jsdom throws "not implemented" on the bare `window.matchMedia` property, and
 * theme_core.js calls it to resolve the OS colour-scheme preference. The stub
 * defaults to `matches: false` (light); tests that care about the dark-OS
 * branch pass their own fake in, since both modules take matchMedia as an
 * argument rather than reaching for the global.
 *
 * Deliberately NOT stubbed here: `fetch`. Tests that exercise session_sync
 * need to assert on the calls it makes, so each passes its own fake in — the
 * module takes `fetchFn` as an argument for that reason.
 */

import 'fake-indexeddb/auto';

if (typeof window.matchMedia !== 'function') {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
