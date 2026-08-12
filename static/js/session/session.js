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
  goTo,
  isFinished,
  next,
  pause,
  previous,
  resume,
  reveal,
  skip,
  toPayload,
} from './session_core.js';
import { interpret } from './session_inference.js';
import {
  latestUnfinished,
  loadLexicon,
  openDb,
  saveLexicon,
  saveSession,
} from './session_db.js';
import { csrfToken, drainQueue, pushSession } from './session_sync.js';
import {
  paint,
  renderQuestion,
  renderSetup,
  renderStorageWarning,
  renderSummary,
  screenFor,
} from './session_ui.js';

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
 * @param {object} options.store - Persistence, real or no-op.
 * @param {string} options.urlTemplate - With WINE_TYPE to substitute.
 * @param {string} options.wineType
 * @param {Function} options.fetchFn
 * @returns {Promise<object|null>}
 */
export async function fetchLexicon({ store, urlTemplate, wineType, fetchFn }) {
  const url = urlTemplate.replace('WINE_TYPE', wineType);
  try {
    const response = await fetchFn(url, { credentials: 'same-origin' });
    if (response.ok) {
      const payload = await response.json();
      await store.saveLexicon(wineType, payload);
      return payload;
    }
  } catch (e) {
    /* Offline. Fall through to whatever we cached. */
  }
  return store.loadLexicon(wineType);
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
  // A session that cannot persist locally is worth far more than no session
  // at all, so a database that will not open is a degraded mode rather than a
  // failure. Everything still works; it just would not survive a reload, and
  // the taster is told so rather than finding out the hard way.
  let database = db;
  let storageWorks = true;
  if (!database) {
    try {
      database = await openDb();
    } catch (e) {
      database = null;
      storageWorks = false;
    }
  }

  let steps = [];
  let payload = null;
  let state = null;

  /** Persistence, or a no-op when the database would not open. */
  const store = {
    save: (value) =>
      database ? saveSession(database, value).catch(() => {}) : Promise.resolve(),
    saveLexicon: (wineType, value) =>
      database ? saveLexicon(database, wineType, value).catch(() => {}) : Promise.resolve(),
    loadLexicon: (wineType) =>
      database ? loadLexicon(database, wineType).catch(() => null) : Promise.resolve(null),
    latestUnfinished: () =>
      database ? latestUnfinished(database).catch(() => null) : Promise.resolve(null),
  };

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
    store.save(state);
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
    // Direct jumps from the phase rail, the question rail, and every line of
    // the summary. Moving around the session should not mean stepping through
    // answers you were happy with.
    onJump: (index) => commit(goTo(steps, state, index, now())),
    // The summary is reachable once everything is answered, without walking
    // off the end of the last phase.
    onReview: () => commit(goTo(steps, state, steps.length, now())),
    onPause: () => commit(pause(steps, state, now())),
    onResume: () => commit(resume(state, now())),
    onReveal: (actual) => {
      state = reveal(state, { ...state.actual, ...actual }, now());
      store.save(state);
    },
    onSave: async () => {
      state = complete(steps, state, now());
      await store.save(state);
      await push();
      // The journal is server-rendered, so a save with no network should not
      // navigate into a page that cannot load. The session is safely on disk
      // and the queue will deliver it.
      if (navigator.onLine) window.location.assign(bootstrap.journal_url);
      else render();
    },
  };

  function render() {
    const screen = renderScreen();
    // The warning sits above whatever screen follows and is repainted with
    // it, because it stays true for the whole session.
    if (!storageWorks) mount.replaceChildren(renderStorageWarning(), screen);
    else paint(mount, screen);
  }

  function renderScreen() {
    if (!state) {
      return renderSetup({ wineTypes: bootstrap.wine_types, onStart: begin });
    }
    if (screenFor(steps, state) === 'summary') {
      return renderSummary({
        steps,
        state,
        // Computed here rather than fetched: the end of a session is exactly
        // when the network is least likely to be there.
        reading: interpret(payload || { phases: [] }, state),
        labelFor,
        handlers,
      });
    }
    return renderQuestion({ steps, state, now: now(), handlers });
  }

  async function begin(wineType, wine) {
    payload = await fetchLexicon({
      store,
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
  const unfinished = await store.latestUnfinished();
  if (unfinished) {
    const cached = (await store.loadLexicon(unfinished.wineType)) || {
      phases: [],
      version: '',
    };
    if (!isFinished(buildSteps(cached), unfinished)) {
      payload = cached;
      steps = buildSteps(payload);
      state = unfinished;
    }
  }

  render();

  // Drain whatever the last visit could not deliver, and again whenever the
  // network comes back.
  const drain = () =>
    database
      ? drainQueue({
          db: database,
          url: bootstrap.sync_url,
          fetchFn,
          cookieString: document.cookie,
          stepsFor: () => steps,
        }).catch(() => {})
      : Promise.resolve();
  window.addEventListener('online', drain);
  drain();

  return {
    getState: () => state,
    getSteps: () => steps,
    render,
    drain,
    storageWorks,
  };
}

const mount = document.getElementById('session-app');
const bootstrapEl = document.getElementById('session-bootstrap');
if (mount && bootstrapEl) {
  startSessionApp({ mount, bootstrap: JSON.parse(bootstrapEl.textContent) });
}
