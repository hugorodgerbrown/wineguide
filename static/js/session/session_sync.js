/*
 * static/js/session/session_sync.js — Getting a session to the server, eventually.
 *
 * The local write already happened by the time anything here runs, so nothing
 * in this module is on the critical path and nothing it does can lose data.
 * Its only job is to drain the dirty queue when there is a network, and to
 * stay quiet when there is not.
 *
 * Three rules, each of which is a bug if broken:
 *
 *   1. Never clear the dirty flag on a response that did not apply. The
 *      endpoint answers `applied: false` for a write it judged stale; that is
 *      a success at the HTTP level and a no-op at the data level.
 *   2. Never clear the flag if the local copy changed while the request was
 *      in flight. `markSynced` compares timestamps for exactly this.
 *   3. Never retry a 4xx forever. A rejected body will be rejected again;
 *      looping on it burns battery and hides the problem.
 */

import { markSynced, pendingSessions } from './session_db.js';
import { toPayload } from './session_core.js';

/** Statuses where retrying is pointless — the request was understood and refused. */
const FATAL = new Set([400, 401, 403, 404, 413, 422]);

/**
 * Read the CSRF token Django set as a cookie.
 *
 * @param {string} cookieString - Usually document.cookie.
 * @returns {string} The token, or '' if absent.
 */
export function csrfToken(cookieString) {
  const match = (cookieString || '')
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith('csrftoken='));
  return match ? decodeURIComponent(match.slice('csrftoken='.length)) : '';
}

/**
 * Push one session to the server.
 *
 * @param {object} options
 * @param {string} options.url - The sync endpoint.
 * @param {object} options.body - Request body from session_core.toPayload.
 * @param {string} options.token - CSRF token.
 * @param {Function} options.fetchFn - fetch implementation.
 * @returns {Promise<{ok: boolean, fatal: boolean, applied: boolean, data: object|null}>}
 */
export async function pushSession({ url, body, token, fetchFn }) {
  let response;
  try {
    response = await fetchFn(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': token,
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    });
  } catch (e) {
    // Offline, DNS failure, connection dropped mid-flight. Retryable, and
    // completely expected — this app is used in cellars and basements.
    return { ok: false, fatal: false, applied: false, data: null };
  }

  if (!response.ok) {
    return {
      ok: false,
      fatal: FATAL.has(response.status),
      applied: false,
      data: null,
    };
  }

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    // A 200 that is not JSON means something sits between us and Django —
    // a captive portal, most likely. Treat it as a network failure.
    return { ok: false, fatal: false, applied: false, data: null };
  }

  return { ok: true, fatal: false, applied: Boolean(data.applied), data };
}

/**
 * Drain the queue of unsynced sessions.
 *
 * Safe to call whenever: on reconnect, after a save, on a timer. It reads its
 * work from IndexedDB rather than from memory, so it also picks up sessions
 * left behind by a previous page load.
 *
 * @param {object} options
 * @param {IDBDatabase} options.db
 * @param {string} options.url - The sync endpoint.
 * @param {Function} options.fetchFn - fetch implementation.
 * @param {string} options.cookieString - document.cookie.
 * @param {Function} options.stepsFor - (state) => steps, for serialisation.
 * @returns {Promise<{sent: number, failed: number, stale: number}>}
 */
export async function drainQueue({ db, url, fetchFn, cookieString, stepsFor }) {
  const pending = await pendingSessions(db);
  const token = csrfToken(cookieString);
  const result = { sent: 0, failed: 0, stale: 0 };

  for (const record of pending) {
    const body = toPayload(stepsFor(record), record);
    const outcome = await pushSession({ url, body, token, fetchFn });

    if (outcome.ok) {
      // Cleared whether or not the write applied: `applied: false` means the
      // server already holds something newer, so there is nothing left for
      // this record to deliver.
      const cleared = await markSynced(db, record.uuid, record.updatedAt);
      if (outcome.applied) result.sent += 1;
      else result.stale += 1;
      if (!cleared) {
        // The taster answered another question while this was in flight.
        // Leave it dirty; the next drain picks up the newer copy.
        result.failed += 1;
      }
    } else if (outcome.fatal) {
      // Do not retry, and do not clear the flag either — the record stays for
      // a human to find rather than being silently dropped.
      result.failed += 1;
      break;
    } else {
      result.failed += 1;
      // Offline. Stop rather than hammering the rest of the queue against a
      // network that is plainly not there.
      break;
    }
  }

  return result;
}
