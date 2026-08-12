/*
 * static/js/session/session_db.js — Local persistence for a tasting session.
 *
 * IndexedDB rather than localStorage: the payload is structured and the writes
 * are frequent, and localStorage is synchronous — every write would block the
 * main thread between a tap and the next prompt, which is the one place PRD §8
 * gives a latency budget.
 *
 * Two stores:
 *
 *   sessions   the session state, keyed by uuid, with a `dirty` flag marking
 *              the ones the server has not acknowledged.
 *   lexicons   payloads, keyed by wine style, so a second session can start
 *              with no connectivity at all.
 *
 * Every write happens before the corresponding network attempt, never after.
 * That ordering is the whole offline story: the tap is durable the moment it
 * happens, and the network is an optimisation that catches up later.
 *
 * All exports take the database as an argument rather than reaching for a
 * module-level singleton, so tests can open a fresh one per case and no test
 * can leak state into the next.
 */

export const DB_NAME = 'wineguide';
export const DB_VERSION = 1;
export const SESSIONS = 'sessions';
export const LEXICONS = 'lexicons';

/**
 * Wrap an IDBRequest in a promise.
 *
 * @param {IDBRequest} request
 * @returns {Promise<*>}
 */
function promisify(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * How long to wait for the database before giving up on it.
 *
 * IndexedDB can leave an open request pending with no event at all — not
 * success, not error, not even `blocked`. A second tab part-way through a
 * version upgrade will do it, so will a `deleteDatabase` that never completed,
 * and so will a browser under storage pressure. Without a bound, the session
 * page waits on that promise forever and the taster sees an empty screen with
 * nothing to explain it.
 *
 * Generous, because a cold open on a slow phone is not instant, and the cost
 * of being wrong is only that the session runs without local persistence.
 */
export const OPEN_TIMEOUT_MS = 3000;

/**
 * Open (and if necessary create) the database.
 *
 * Rejects rather than hanging — see `OPEN_TIMEOUT_MS`. The caller is expected
 * to carry on without persistence rather than refusing to start: a tasting
 * that syncs but would not survive a reload is worth far more than no tasting
 * at all.
 *
 * @param {IDBFactory} [factory] - Defaults to the global indexedDB.
 * @param {number} [timeoutMs]
 * @returns {Promise<IDBDatabase>}
 */
export function openDb(factory = globalThis.indexedDB, timeoutMs = OPEN_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    if (!factory) {
      reject(new Error('IndexedDB unavailable'));
      return;
    }

    let settled = false;
    const finish = (fn, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      fn(value);
    };

    const timer = setTimeout(
      () => finish(reject, new Error('IndexedDB did not respond')),
      timeoutMs,
    );

    let request;
    try {
      request = factory.open(DB_NAME, DB_VERSION);
    } catch (e) {
      // Firefox in permanent-private mode throws synchronously here.
      finish(reject, e);
      return;
    }

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(SESSIONS)) {
        const store = db.createObjectStore(SESSIONS, { keyPath: 'uuid' });
        // Queried on every reconnect to find what still needs sending.
        store.createIndex('dirty', 'dirty', { unique: false });
        store.createIndex('updatedAt', 'updatedAt', { unique: false });
      }
      if (!db.objectStoreNames.contains(LEXICONS)) {
        db.createObjectStore(LEXICONS, { keyPath: 'wineType' });
      }
    };
    // Another tab is holding the old version open. It may close in a moment,
    // but the taster should not be made to wait and guess.
    request.onblocked = () =>
      finish(reject, new Error('IndexedDB blocked by another tab'));
    request.onsuccess = () => finish(resolve, request.result);
    request.onerror = () => finish(reject, request.error);
  });
}

/**
 * Run a transaction and resolve when it has actually committed.
 *
 * Resolving on the request rather than the transaction is the classic
 * IndexedDB bug: the value is available before the write is durable, so a
 * page closed in between loses it — which is exactly the case this store
 * exists to survive.
 *
 * @param {IDBDatabase} db
 * @param {string|string[]} stores
 * @param {IDBTransactionMode} mode
 * @param {(tx: IDBTransaction) => IDBRequest} work
 * @returns {Promise<*>}
 */
function transact(db, stores, mode, work) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(stores, mode);
    let result;
    const request = work(tx);
    if (request) {
      request.onsuccess = () => {
        result = request.result;
      };
    }
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

/**
 * Write a session, marking whether the server has it.
 *
 * @param {IDBDatabase} db
 * @param {object} state - Session state from session_core.
 * @param {{dirty?: boolean}} [options] - dirty defaults to true.
 * @returns {Promise<void>}
 */
export function saveSession(db, state, { dirty = true } = {}) {
  // `dirty` is stored as 0/1, not a boolean: IndexedDB cannot index boolean
  // values, and an index on it is how the sync queue finds its work.
  const record = { ...state, dirty: dirty ? 1 : 0 };
  return transact(db, SESSIONS, 'readwrite', (tx) =>
    tx.objectStore(SESSIONS).put(record),
  );
}

/**
 * Read one session back.
 *
 * @param {IDBDatabase} db
 * @param {string} uuid
 * @returns {Promise<object|undefined>}
 */
export function loadSession(db, uuid) {
  return transact(db, SESSIONS, 'readonly', (tx) =>
    tx.objectStore(SESSIONS).get(uuid),
  );
}

/**
 * Every session the server has not acknowledged, oldest change first.
 *
 * Oldest first so a backlog drains in the order it happened; the endpoint
 * settles conflicts by timestamp anyway, but replaying in order keeps the
 * server's view sane while it catches up.
 *
 * @param {IDBDatabase} db
 * @returns {Promise<Array<object>>}
 */
export async function pendingSessions(db) {
  const all = await transact(db, SESSIONS, 'readonly', (tx) =>
    tx.objectStore(SESSIONS).index('dirty').getAll(1),
  );
  return (all || []).sort((a, b) => String(a.updatedAt).localeCompare(b.updatedAt));
}

/**
 * Mark a session as acknowledged by the server.
 *
 * Compares `updatedAt` before clearing the flag: a tap made while the request
 * was in flight leaves the local copy newer than what was sent, and clearing
 * the flag then would strand that tap locally forever.
 *
 * @param {IDBDatabase} db
 * @param {string} uuid
 * @param {string} syncedUpdatedAt - The updatedAt that was sent.
 * @returns {Promise<boolean>} Whether the flag was cleared.
 */
export async function markSynced(db, uuid, syncedUpdatedAt) {
  const stored = await loadSession(db, uuid);
  if (!stored) return false;
  if (stored.updatedAt !== syncedUpdatedAt) return false;
  await saveSession(db, stripFlag(stored), { dirty: false });
  return true;
}

/**
 * Return a stored record without its storage-only fields.
 *
 * @param {object} record
 * @returns {object} The session state as session_core knows it.
 */
export function stripFlag(record) {
  const { dirty: _dirty, ...state } = record;
  return state;
}

/**
 * The most recently updated unfinished session, if there is one.
 *
 * What "resume where you left off" reads on load — a taster who closed the
 * tab mid-phase should find the session waiting, not have to start again
 * (PRD §6.2).
 *
 * @param {IDBDatabase} db
 * @returns {Promise<object|null>}
 */
export async function latestUnfinished(db) {
  const all = await transact(db, SESSIONS, 'readonly', (tx) =>
    tx.objectStore(SESSIONS).getAll(),
  );
  const open = (all || []).filter((s) => s.status === 'in_progress');
  if (!open.length) return null;
  open.sort((a, b) => String(b.updatedAt).localeCompare(a.updatedAt));
  return stripFlag(open[0]);
}

/**
 * Cache a lexicon payload for a wine style.
 *
 * @param {IDBDatabase} db
 * @param {string} wineType
 * @param {object} payload
 * @returns {Promise<void>}
 */
export function saveLexicon(db, wineType, payload) {
  return transact(db, LEXICONS, 'readwrite', (tx) =>
    tx.objectStore(LEXICONS).put({ wineType, payload }),
  );
}

/**
 * Read a cached lexicon payload.
 *
 * @param {IDBDatabase} db
 * @param {string} wineType
 * @returns {Promise<object|null>}
 */
export async function loadLexicon(db, wineType) {
  const record = await transact(db, LEXICONS, 'readonly', (tx) =>
    tx.objectStore(LEXICONS).get(wineType),
  );
  return record ? record.payload : null;
}

/**
 * Delete a session from local storage.
 *
 * @param {IDBDatabase} db
 * @param {string} uuid
 * @returns {Promise<void>}
 */
export function deleteSession(db, uuid) {
  return transact(db, SESSIONS, 'readwrite', (tx) =>
    tx.objectStore(SESSIONS).delete(uuid),
  );
}
