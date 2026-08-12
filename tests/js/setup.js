/*
 * tests/js/setup.js — Vitest global setup, registered via vitest.config.mjs's
 * `setupFiles`. Runs once per test file, before that file's module graph is
 * imported.
 *
 * jsdom throws "not implemented" on the bare `window.matchMedia` property, and
 * theme_core.js calls it to resolve the OS colour-scheme preference. The stub
 * defaults to `matches: false` (light); tests that care about the dark-OS
 * branch pass their own fake in, since both modules take matchMedia as an
 * argument rather than reaching for the global.
 */

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
