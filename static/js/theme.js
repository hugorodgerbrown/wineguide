/*
 * static/js/theme.js — Binds the theme toggle to the document.
 *
 * The button is rendered `hidden` in base.html and revealed here, so a reader
 * whose JavaScript never runs is not shown a control that does nothing. This
 * module only wires events; the rules live in theme_core.js, where they are
 * unit-tested.
 *
 * The stored theme is applied twice: once by the inline script in <head>
 * (before first paint, to avoid a flash) and once here, which is a no-op when
 * the inline script already ran. Doing it here as well keeps this module
 * correct on its own if that inline script is ever dropped.
 */

import {
  applyTheme,
  currentTheme,
  nextTheme,
  readStoredTheme,
  storeTheme,
} from './theme_core.js';

/**
 * Wire up the theme toggle.
 *
 * @param {Document} doc - The document to bind against.
 * @param {Storage} storage - Usually window.localStorage.
 * @param {(query: string) => {matches: boolean}} matchMedia - window.matchMedia.
 * @returns {HTMLElement|null} The button, or null if the page has no toggle.
 */
export function initThemeToggle(doc, storage, matchMedia) {
  const root = doc.documentElement;
  const stored = readStoredTheme(storage);
  if (stored) {
    applyTheme(root, stored);
  }

  const button = doc.getElementById('theme-toggle');
  if (!button) {
    return null;
  }

  const sync = () => {
    button.setAttribute(
      'aria-pressed',
      currentTheme(root, matchMedia) === 'dark' ? 'true' : 'false',
    );
  };

  button.addEventListener('click', () => {
    const theme = nextTheme(currentTheme(root, matchMedia));
    applyTheme(root, theme);
    storeTheme(storage, theme);
    sync();
  });

  button.hidden = false;
  sync();
  return button;
}

/* Self-wire on load. Harmless under test: with no #theme-toggle in the
 * document this returns null, and each test then calls initThemeToggle
 * explicitly against the DOM it built. */
if (typeof document !== 'undefined') {
  initThemeToggle(document, window.localStorage, window.matchMedia.bind(window));
}
