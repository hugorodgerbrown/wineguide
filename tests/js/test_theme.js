/*
 * tests/js/test_theme.js — Tests for the theme toggle's DOM wiring.
 *
 * theme.js self-wires on import against whatever document exists; at import
 * time here that is an empty jsdom page with no toggle, so the self-wiring is
 * a no-op and each test drives initThemeToggle directly. The button is
 * deliberately markup-shaped the way base.html renders it — `hidden`, with
 * aria-pressed="false" — so a change to that markup breaks a test here rather
 * than silently shipping an unusable control.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { initThemeToggle } from '../../static/js/theme.js';
import { STORAGE_KEY } from '../../static/js/theme_core.js';

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = value;
    },
    data,
  };
}

const matchLight = () => ({ matches: false });
const matchDark = () => ({ matches: true });

function renderToggle() {
  document.documentElement.removeAttribute('data-theme');
  document.body.innerHTML = `
    <button id="theme-toggle" type="button" hidden aria-pressed="false">
      <span class="theme-toggle__label">Dark mode</span>
    </button>`;
  return document.getElementById('theme-toggle');
}

describe('initThemeToggle', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme');
    document.body.innerHTML = '';
  });

  it('reveals the button, which the server renders hidden', () => {
    const button = renderToggle();
    expect(button.hidden).toBe(true);

    initThemeToggle(document, fakeStorage(), matchLight);

    expect(button.hidden).toBe(false);
  });

  it('applies the stored theme on load', () => {
    renderToggle();

    initThemeToggle(document, fakeStorage({ [STORAGE_KEY]: 'dark' }), matchLight);

    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('leaves data-theme unset when nothing is stored, so CSS decides', () => {
    renderToggle();

    initThemeToggle(document, fakeStorage(), matchDark);

    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
  });

  it('flips the theme on click', () => {
    const button = renderToggle();
    initThemeToggle(document, fakeStorage(), matchLight);

    button.click();
    expect(document.documentElement.dataset.theme).toBe('dark');

    button.click();
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('persists the choice', () => {
    const button = renderToggle();
    const storage = fakeStorage();
    initThemeToggle(document, storage, matchLight);

    button.click();

    expect(storage.data[STORAGE_KEY]).toBe('dark');
  });

  it('flips away from the OS preference on the first press', () => {
    const button = renderToggle();
    initThemeToggle(document, fakeStorage(), matchDark);

    button.click();

    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('keeps aria-pressed in step with the theme', () => {
    const button = renderToggle();
    initThemeToggle(document, fakeStorage(), matchLight);
    expect(button.getAttribute('aria-pressed')).toBe('false');

    button.click();
    expect(button.getAttribute('aria-pressed')).toBe('true');

    button.click();
    expect(button.getAttribute('aria-pressed')).toBe('false');
  });

  it('reports aria-pressed=true on load under a dark OS preference', () => {
    const button = renderToggle();

    initThemeToggle(document, fakeStorage(), matchDark);

    expect(button.getAttribute('aria-pressed')).toBe('true');
  });

  it('does nothing on a page with no toggle', () => {
    document.body.innerHTML = '<p>No toggle here.</p>';

    expect(initThemeToggle(document, fakeStorage(), matchLight)).toBeNull();
  });

  it('still applies the stored theme on a page with no toggle', () => {
    document.body.innerHTML = '';

    initThemeToggle(document, fakeStorage({ [STORAGE_KEY]: 'dark' }), matchLight);

    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('survives a storage that throws on every access', () => {
    const button = renderToggle();
    const throwing = {
      getItem: vi.fn(() => {
        throw new Error('storage disabled');
      }),
      setItem: vi.fn(() => {
        throw new Error('storage disabled');
      }),
    };

    initThemeToggle(document, throwing, matchLight);
    button.click();

    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(throwing.setItem).toHaveBeenCalled();
  });
});
