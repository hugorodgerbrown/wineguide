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
  previous,
  reveal,
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
 * @param {string} [options.version] - Pin to one published vocabulary.
 * @param {Function} options.fetchFn
 * @returns {Promise<object|null>}
 */
export async function fetchLexicon({
  store,
  urlTemplate,
  wineType,
  version = '',
  fetchFn,
}) {
  const base = urlTemplate.replace('WINE_TYPE', wineType);
  const url = version ? `${base}?version=${encodeURIComponent(version)}` : base;
  try {
    const response = await fetchFn(url, { credentials: 'same-origin' });
    if (response.ok) {
      const payload = await response.json();
      // Cached under the style alone, which is what a new session asks for.
      // A pinned fetch is for reopening an old note and must not displace it.
      if (!version) await store.saveLexicon(wineType, payload);
      return payload;
    }
  } catch (e) {
    /* Offline. Fall through to whatever we cached. */
  }
  const cached = await store.loadLexicon(wineType);
  // A pinned request that fell back to the cache is only usable if the cache
  // happens to hold that same version; the wrong questions are worse than a
  // clear failure.
  if (version && cached && cached.version !== version) return null;
  return cached;
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
  // Screen-local, not session state: whether the "why it matters" sheet is
  // open is not something worth persisting or syncing, and it should not
  // survive moving to another question.
  let rubricOpen = false;

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
    onNext: () => {
      rubricOpen = false;
      commit(next(steps, state, now()));
    },
    onBack: () => {
      rubricOpen = false;
      commit(previous(steps, state, now()));
    },
    // Direct jumps from the phase rail, the question rail, and every line of
    // the summary. Moving around the session should not mean stepping through
    // answers you were happy with.
    onJump: (index) => {
      rubricOpen = false;
      commit(goTo(steps, state, index, now()));
    },
    onRubric: () => {
      rubricOpen = !rubricOpen;
      render();
    },
    // The summary is reachable once everything is answered, without walking
    // off the end of the last phase.
    onReview: () => commit(goTo(steps, state, steps.length, now())),
    // Finish where you stand. Same path as saving from the summary, so a
    // half-finished tasting is stored exactly like a complete one — the
    // journal already distinguishes them by what was answered.
    onFinish: () => handlers.onSave(),
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
    // The wine themes the whole session — accent, paper tint, action bar and
    // the depth ramp the scale swatches are drawn from. One attribute, and
    // every token below it changes.
    if (state) mount.dataset.wine = state.wineType;
    else delete mount.dataset.wine;

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
    return renderQuestion({ steps, state, now: now(), rubricOpen, handlers });
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

  // Reopening a stored note. The server hands over the whole state and the
  // version it was taken against, so the questions on screen are the ones
  // that were actually asked — a note recorded before a question existed must
  // not come back with a gap in it. Written to IndexedDB on arrival, so from
  // here it is an ordinary session: change an answer and it syncs back under
  // the same uuid, which is what makes the upsert idempotent.
  if (bootstrap.session) {
    payload = await fetchLexicon({
      store,
      urlTemplate: bootstrap.lexicon_url,
      wineType: bootstrap.session.wineType,
      version: bootstrap.lexicon_version,
      fetchFn,
    });
    if (payload) {
      steps = buildSteps(payload);
      // The summary is the landing place: someone reopening a note came to
      // change one answer, and every question is one tap from there.
      state = { ...bootstrap.session, cursor: steps.length };
      await store.save(state);
    }
  }

  // Resume rather than restart. Someone who closed the tab mid-phase should
  // find the session where they left it (PRD §6.2, §7) — unless they arrived
  // by asking for a new tasting, in which case resuming is the app ignoring
  // what they just clicked.
  const unfinished =
    state || bootstrap.resume === false ? null : await store.latestUnfinished();
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
