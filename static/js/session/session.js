/*
 * static/js/session/session.js — The controller that wires the session together.
 *
 * Reads the bootstrap JSON the server embedded, then owns the loop:
 *
 *     tap → session_core computes the next state
 *         → session_db writes it            (durable, immediately)
 *         → session_ui repaints             (synchronous, no await)
 *         → session_sync ships it           (whenever it can, in the background)
 *
 * The order matters. The write is awaited before nothing — the repaint does
 * not wait for it, so the next prompt is on screen in the time it takes to
 * build a few DOM nodes, and the durability lands a tick later. The network
 * is never on this path at all.
 *
 * Deliberately not a framework. The whole app is one question at a time; a
 * reactive runtime would be larger than the thing it renders and would put a
 * scheduler between the tap and the paint.
 */

import {
  answer,
  buildSteps,
  complete,
  createSession,
  isFinished,
  next,
  pause,
  previous,
  resume,
  reveal,
  skip,
  toPayload,
} from './session_core.js';
import {
  latestUnfinished,
  loadLexicon,
  openDb,
  saveLexicon,
  saveSession,
} from './session_db.js';
import { csrfToken, drainQueue, pushSession } from './session_sync.js';
import { paint, renderQuestion, renderSetup, renderSummary, screenFor } from './session_ui.js';

/** @returns {string} An ISO timestamp with a UTC offset, as the API requires. */
const now = () => new Date().toISOString();

/**
 * Fetch a lexicon payload, falling back to the local cache when offline.
 *
 * Cache-first would be wrong here — a corrected lexicon should reach a taster
 * who has a network. Network-first with a local fallback means the common
 * case is current and the offline case still works.
 *
 * @param {object} options
 * @param {IDBDatabase} options.db
 * @param {string} options.urlTemplate - With WINE_TYPE to substitute.
 * @param {string} options.wineType
 * @param {Function} options.fetchFn
 * @returns {Promise<object|null>}
 */
export async function fetchLexicon({ db, urlTemplate, wineType, fetchFn }) {
  const url = urlTemplate.replace('WINE_TYPE', wineType);
  try {
    const response = await fetchFn(url, { credentials: 'same-origin' });
    if (response.ok) {
      const payload = await response.json();
      await saveLexicon(db, wineType, payload);
      return payload;
    }
  } catch (e) {
    /* Offline. Fall through to whatever we cached. */
  }
  return loadLexicon(db, wineType);
}

/**
 * Start the session app inside `mount`.
 *
 * @param {object} options
 * @param {HTMLElement} options.mount
 * @param {object} options.bootstrap - From the embedded JSON.
 * @param {Function} [options.fetchFn]
 * @param {IDBDatabase} [options.db]
 * @returns {Promise<object>} A small handle, for tests.
 */
export async function startSessionApp({
  mount,
  bootstrap,
  fetchFn = globalThis.fetch.bind(globalThis),
  db = null,
}) {
  const database = db || (await openDb());
  let steps = [];
  let payload = null;
  let state = null;

  const labelFor = (questionCode, optionCode) => {
    for (const step of steps) {
      if (step.question.code !== questionCode) continue;
      for (const option of step.question.options) {
        if (option.code === optionCode) return option.label;
        const child = (option.children || []).find((c) => c.code === optionCode);
        if (child) return child.label;
      }
    }
    return optionCode;
  };

  /** Persist, then repaint. Never the other way round. */
  const commit = (nextState) => {
    state = nextState;
    // Not awaited: the write is durable within a tick and the taster should
    // not wait for a disk to see the next prompt. A rejection is logged
    // rather than surfaced — there is nothing they could do about it, and
    // the sync queue is the backstop.
    saveSession(database, state).catch(() => {});
    render();
    schedulePush();
  };

  let pushTimer = null;
  const schedulePush = () => {
    // Coalesced: a taster tapping through a multi-select would otherwise
    // fire a request per chip. Two seconds of quiet is well inside the
    // window where losing the tail matters, because the tail is already on
    // disk.
    if (pushTimer) clearTimeout(pushTimer);
    pushTimer = setTimeout(() => push(), 2000);
  };

  const push = async () => {
    if (!state) return;
    await pushSession({
      url: bootstrap.sync_url,
      body: toPayload(steps, state),
      token: csrfToken(document.cookie),
      fetchFn,
    });
  };

  const handlers = {
    onAnswer: (code) => commit(answer(steps, state, code, now())),
    onSkip: () => commit(next(steps, skip(steps, state, now()), now())),
    onNext: () => commit(next(steps, state, now())),
    onBack: () => commit(previous(steps, state, now())),
    onPause: () => commit(pause(steps, state, now())),
    onResume: () => commit(resume(state, now())),
    onReveal: (actual) => {
      state = reveal(state, { ...state.actual, ...actual }, now());
      saveSession(database, state).catch(() => {});
    },
    onSave: async () => {
      state = complete(steps, state, now());
      await saveSession(database, state);
      await push();
      // The journal is server-rendered, so a save with no network should not
      // navigate into a page that cannot load. The session is safely on disk
      // and the queue will deliver it.
      if (navigator.onLine) window.location.assign(bootstrap.journal_url);
      else render();
    },
  };

  function render() {
    if (!state) {
      paint(
        mount,
        renderSetup({ wineTypes: bootstrap.wine_types, onStart: begin }),
      );
      return;
    }
    if (screenFor(steps, state) === 'summary') {
      paint(mount, renderSummary({ steps, state, labelFor, handlers }));
      return;
    }
    paint(mount, renderQuestion({ steps, state, now: now(), handlers }));
  }

  async function begin(wineType, wine) {
    payload = await fetchLexicon({
      db: database,
      urlTemplate: bootstrap.lexicon_url,
      wineType,
      fetchFn,
    });
    if (!payload) {
      paint(
        mount,
        Object.assign(document.createElement('p'), {
          className: 'rounded-card border border-rule bg-paper-raised p-6 text-ink-muted',
          textContent:
            'That style has not been downloaded yet, and there is no connection. ' +
            'Try one you have tasted before, or reconnect.',
        }),
      );
      return;
    }
    steps = buildSteps(payload);
    commit(
      createSession({
        payload,
        uuid: crypto.randomUUID(),
        now: now(),
        wine,
      }),
    );
  }

  // Resume rather than restart. Someone who closed the tab mid-phase should
  // find the session where they left it (PRD §6.2, §7).
  const unfinished = await latestUnfinished(database);
  if (unfinished && !isFinished(buildSteps(await cachedPayload(unfinished)), unfinished)) {
    payload = await cachedPayload(unfinished);
    steps = buildSteps(payload);
    state = unfinished;
  }

  async function cachedPayload(forState) {
    return (
      (await loadLexicon(database, forState.wineType)) || { phases: [], version: '' }
    );
  }

  render();

  // Drain whatever the last visit could not deliver, and again whenever the
  // network comes back.
  const drain = () =>
    drainQueue({
      db: database,
      url: bootstrap.sync_url,
      fetchFn,
      cookieString: document.cookie,
      stepsFor: () => steps,
    }).catch(() => {});
  window.addEventListener('online', drain);
  drain();

  return { getState: () => state, getSteps: () => steps, render, drain };
}

const mount = document.getElementById('session-app');
const bootstrapEl = document.getElementById('session-bootstrap');
if (mount && bootstrapEl) {
  startSessionApp({ mount, bootstrap: JSON.parse(bootstrapEl.textContent) });
}
