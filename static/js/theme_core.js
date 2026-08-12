/*
 * static/js/theme_core.js — Theme logic, with no DOM wiring.
 *
 * Kept separate from theme.js so the rules (what is stored, what wins when
 * storage is empty, what the toggle flips to) can be unit-tested directly
 * without standing up a document and firing events. theme.js is the thin
 * layer that binds these to the button.
 *
 * Every storage access is wrapped: localStorage throws on access in a
 * private-mode Safari window and when a browser blocks site data, and a
 * theme toggle is not worth breaking the page over.
 */

export const STORAGE_KEY = 'wineguide.theme';
export const LIGHT = 'light';
export const DARK = 'dark';

/**
 * Read the stored theme preference.
 *
 * @param {Storage} storage - Usually window.localStorage.
 * @returns {'light'|'dark'|null} The stored theme, or null if unset or unreadable.
 */
export function readStoredTheme(storage) {
  try {
    const value = storage.getItem(STORAGE_KEY);
    return value === LIGHT || value === DARK ? value : null;
  } catch (e) {
    return null;
  }
}

/**
 * Persist a theme preference, ignoring a storage that refuses to write.
 *
 * @param {Storage} storage - Usually window.localStorage.
 * @param {'light'|'dark'} theme - The theme to store.
 * @returns {boolean} True if the value was written.
 */
export function storeTheme(storage, theme) {
  try {
    storage.setItem(STORAGE_KEY, theme);
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * The theme currently in force on the document.
 *
 * With nothing stored there is no data-theme attribute and the stylesheet's
 * prefers-color-scheme rules decide, so the OS preference is the answer.
 *
 * @param {HTMLElement} root - The <html> element.
 * @param {(query: string) => {matches: boolean}} matchMedia - window.matchMedia.
 * @returns {'light'|'dark'} The effective theme.
 */
export function currentTheme(root, matchMedia) {
  const explicit = root.dataset.theme;
  if (explicit === LIGHT || explicit === DARK) {
    return explicit;
  }
  return matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
}

/**
 * The theme a toggle press moves to.
 *
 * @param {'light'|'dark'} theme - The theme in force.
 * @returns {'light'|'dark'} The other one.
 */
export function nextTheme(theme) {
  return theme === DARK ? LIGHT : DARK;
}

/**
 * Apply a theme to the document.
 *
 * @param {HTMLElement} root - The <html> element.
 * @param {'light'|'dark'} theme - The theme to apply.
 * @returns {'light'|'dark'} The theme applied, for chaining.
 */
export function applyTheme(root, theme) {
  root.dataset.theme = theme;
  return theme;
}
