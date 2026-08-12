/*
 * tests/js/test_theme_core.js — Unit tests for the theme rules.
 *
 * These cover the parts with no DOM wiring: what is read from storage, what
 * happens when storage throws, and which theme a press moves to. The wiring
 * itself is covered in test_theme.js.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import {
  DARK,
  LIGHT,
  STORAGE_KEY,
  applyTheme,
  currentTheme,
  nextTheme,
  readStoredTheme,
  storeTheme,
} from '../../static/js/theme_core.js';

/** A localStorage stand-in that can be made to throw, as Safari's does in
 *  private mode and as any browser's does when site data is blocked. */
function fakeStorage({ throws = false, initial = {} } = {}) {
  const data = { ...initial };
  return {
    getItem(key) {
      if (throws) throw new Error('storage disabled');
      return key in data ? data[key] : null;
    },
    setItem(key, value) {
      if (throws) throw new Error('storage disabled');
      data[key] = value;
    },
    data,
  };
}

const matchDark = () => ({ matches: true });
const matchLight = () => ({ matches: false });

describe('readStoredTheme', () => {
  it('returns a stored theme', () => {
    const storage = fakeStorage({ initial: { [STORAGE_KEY]: DARK } });
    expect(readStoredTheme(storage)).toBe(DARK);
  });

  it('returns null when nothing is stored', () => {
    expect(readStoredTheme(fakeStorage())).toBeNull();
  });

  it('rejects a value that is not a known theme', () => {
    const storage = fakeStorage({ initial: { [STORAGE_KEY]: 'chartreuse' } });
    expect(readStoredTheme(storage)).toBeNull();
  });

  it('returns null rather than throwing when storage is unavailable', () => {
    expect(readStoredTheme(fakeStorage({ throws: true }))).toBeNull();
  });
});

describe('storeTheme', () => {
  it('writes the preference under the namespaced key', () => {
    const storage = fakeStorage();
    expect(storeTheme(storage, DARK)).toBe(true);
    expect(storage.data[STORAGE_KEY]).toBe(DARK);
  });

  it('reports failure rather than throwing when storage is unavailable', () => {
    expect(storeTheme(fakeStorage({ throws: true }), DARK)).toBe(false);
  });
});

describe('currentTheme', () => {
  let root;

  beforeEach(() => {
    root = document.createElement('html');
  });

  it('prefers an explicit data-theme over the OS preference', () => {
    root.dataset.theme = LIGHT;
    expect(currentTheme(root, matchDark)).toBe(LIGHT);
  });

  it('falls back to the OS preference when unset', () => {
    expect(currentTheme(root, matchDark)).toBe(DARK);
    expect(currentTheme(root, matchLight)).toBe(LIGHT);
  });

  it('ignores an unrecognised data-theme', () => {
    root.dataset.theme = 'chartreuse';
    expect(currentTheme(root, matchLight)).toBe(LIGHT);
  });
});

describe('nextTheme', () => {
  it('flips between the two themes', () => {
    expect(nextTheme(LIGHT)).toBe(DARK);
    expect(nextTheme(DARK)).toBe(LIGHT);
  });

  it('is its own inverse', () => {
    expect(nextTheme(nextTheme(DARK))).toBe(DARK);
  });
});

describe('applyTheme', () => {
  it('sets data-theme on the element and returns it', () => {
    const root = document.createElement('html');
    expect(applyTheme(root, DARK)).toBe(DARK);
    expect(root.dataset.theme).toBe(DARK);
    expect(root.getAttribute('data-theme')).toBe(DARK);
  });
});
