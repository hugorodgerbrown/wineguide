/*
 * static/js/session/session_core.js — The tasting session, as a state machine.
 *
 * No DOM, no storage, no network. Everything about *what* the session is —
 * which question is showing, what has been answered, whether the phase timer
 * has run out, what gets sent to the server — lives here and is unit-tested
 * directly. session_ui.js draws it, session_db.js persists it, session_sync.js
 * ships it.
 *
 * That split is what makes PRD §8's "<200ms phase transitions" a property of
 * the design rather than something to profile later: answering a question is a
 * function call and an object update. Nothing between the tap and the next
 * prompt touches a network or a database.
 *
 * The state is a plain, serialisable object throughout. Anything held here
 * must survive `structuredClone` into IndexedDB and `JSON.stringify` onto the
 * wire — no class instances, no Dates, no Maps. Times are ISO strings.
 *
 * A session is a flat list of steps built from the payload's phases, plus a
 * cursor. Flattening up front means "next" is `index + 1` in every case,
 * including across a phase boundary, and no caller has to know how phases are
 * shaped.
 */

export const STATUS = {
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  ABANDONED: 'abandoned',
};

/**
 * Build the flat step list from a lexicon payload.
 *
 * @param {object} payload - As returned by the lexicon endpoint.
 * @returns {Array<object>} One entry per question, in running order.
 */
export function buildSteps(payload) {
  const steps = [];
  (payload.phases || []).forEach((phase, phaseIndex) => {
    (phase.questions || []).forEach((question) => {
      steps.push({
        phase: phase.code,
        phaseLabel: phase.label,
        phaseIndex,
        phaseSeconds: phase.seconds,
        question,
      });
    });
  });
  return steps;
}

/**
 * Start a session.
 *
 * The uuid is minted here, before anything is sent anywhere, so a session
 * begun with no connectivity already has the identity it will sync under.
 *
 * @param {object} options
 * @param {object} options.payload - The lexicon payload for this wine style.
 * @param {string} options.uuid - A UUID for this session.
 * @param {string} options.now - ISO timestamp to record as the start.
 * @param {object} [options.wine] - Optional wine identity from setup.
 * @returns {object} A fresh session state.
 */
export function createSession({ payload, uuid, now, wine = {} }) {
  return {
    uuid,
    lexiconVersion: payload.version,
    wineType: payload.wine_type,
    wine: {
      name: wine.name || '',
      producer: wine.producer || '',
      region: wine.region || '',
      vintage: wine.vintage || null,
      blind: Boolean(wine.blind),
    },
    actual: { grape: '', origin: '' },
    status: STATUS.IN_PROGRESS,
    startedAt: now,
    updatedAt: now,
    cursor: 0,
    /** {questionCode: {values: string[], skipped: boolean}} */
    answers: {},
    /** Accumulated ms spent in each phase, keyed by phase code. */
    elapsed: {},
    /** ISO time the current phase was entered, or null while paused. */
    phaseEnteredAt: now,
    paused: false,
  };
}

/**
 * Return the step the cursor is on, or null when the session is past the end.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @returns {object|null}
 */
export function currentStep(steps, state) {
  return steps[state.cursor] || null;
}

/**
 * Return whether every step has been passed.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @returns {boolean}
 */
export function isFinished(steps, state) {
  return state.cursor >= steps.length;
}

/**
 * Record an answer for the current question.
 *
 * Single-select and scale questions replace their answer; multi-select
 * toggles, because a taster who taps "lemon" twice meant to take it off.
 * Answering always clears any earlier skip on that question.
 *
 * Does NOT advance. Advancing is a separate, explicit act — on a multi-select
 * the taster is not finished after the first tap, and auto-advancing a
 * single-select would rob them of the moment to change their mind that PRD §7
 * asks for.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {string} value - The option code tapped.
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function answer(steps, state, value, now) {
  const step = currentStep(steps, state);
  if (!step) return state;

  const code = step.question.code;
  const existing = state.answers[code]?.values || [];
  let values;

  if (step.question.control === 'multi') {
    values = existing.includes(value)
      ? existing.filter((v) => v !== value)
      : [...existing, value];
  } else {
    values = [value];
  }

  return {
    ...state,
    updatedAt: now,
    answers: { ...state.answers, [code]: { values, skipped: false } },
  };
}

/**
 * Mark the current question as skipped.
 *
 * Recorded as an explicit skip rather than an empty answer: PRD §6.1 asks for
 * "genuinely unsure" to be a first-class outcome, not a blank that reads the
 * same as never having got there.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function skip(steps, state, now) {
  const step = currentStep(steps, state);
  if (!step) return state;
  return {
    ...state,
    updatedAt: now,
    answers: {
      ...state.answers,
      [step.question.code]: { values: [], skipped: true },
    },
  };
}

/**
 * Accumulate time spent in the phase being left.
 *
 * @param {object} state
 * @param {string} phase - The phase code being left.
 * @param {string} now - ISO timestamp.
 * @returns {object} Updated elapsed map.
 */
function accrue(state, phase, now) {
  if (!phase || !state.phaseEnteredAt) return state.elapsed;
  const ms = Date.parse(now) - Date.parse(state.phaseEnteredAt);
  if (!Number.isFinite(ms) || ms < 0) return state.elapsed;
  return { ...state.elapsed, [phase]: (state.elapsed[phase] || 0) + ms };
}

/**
 * Move to the next question.
 *
 * Crossing into a new phase banks the time spent in the old one and restarts
 * the clock. Past the last step the cursor stops at the end — `isFinished`
 * becomes true and the summary takes over.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function next(steps, state, now) {
  if (isFinished(steps, state)) return state;

  const leaving = steps[state.cursor];
  const arriving = steps[state.cursor + 1];
  const changedPhase = !arriving || arriving.phase !== leaving.phase;

  return {
    ...state,
    cursor: state.cursor + 1,
    updatedAt: now,
    elapsed: changedPhase ? accrue(state, leaving.phase, now) : state.elapsed,
    phaseEnteredAt: changedPhase ? now : state.phaseEnteredAt,
  };
}

/**
 * Move back one question.
 *
 * Answers are left alone — going back to look at what you put is not the same
 * as wanting to erase it.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function previous(steps, state, now) {
  if (state.cursor <= 0) return state;
  const arriving = steps[state.cursor - 1];
  const leaving = steps[state.cursor];
  const changedPhase = !leaving || arriving.phase !== leaving.phase;

  return {
    ...state,
    cursor: state.cursor - 1,
    updatedAt: now,
    phaseEnteredAt: changedPhase ? now : state.phaseEnteredAt,
  };
}

/**
 * Pause the session.
 *
 * Banks the time spent so far so a pause does not inflate the phase timer.
 * PRD §7 calls this interruption-safety, and it is the difference between the
 * timer being a pacing aid and being a source of stress.
 *
 * @param {object} state
 * @param {Array<object>} steps
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function pause(steps, state, now) {
  if (state.paused) return state;
  const step = currentStep(steps, state);
  return {
    ...state,
    paused: true,
    updatedAt: now,
    elapsed: accrue(state, step?.phase, now),
    phaseEnteredAt: null,
  };
}

/**
 * Resume a paused session.
 *
 * @param {object} state
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function resume(state, now) {
  if (!state.paused) return state;
  return { ...state, paused: false, updatedAt: now, phaseEnteredAt: now };
}

/**
 * Milliseconds spent in a phase, including the stretch currently running.
 *
 * The running stretch is added only for the phase the cursor is actually in.
 * `phaseEnteredAt` is a single clock, so without that check every phase — the
 * ones already finished and the ones not yet reached — would appear to be
 * accruing time along with the live one.
 *
 * The running phase is derived from the cursor rather than stored, so it
 * cannot drift out of step with where the taster actually is.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {string} phase - Phase code.
 * @param {string} now - ISO timestamp.
 * @returns {number} Milliseconds.
 */
export function phaseElapsedMs(steps, state, phase, now) {
  const banked = state.elapsed[phase] || 0;
  const step = currentStep(steps, state);
  if (!step || step.phase !== phase) return banked;
  if (state.paused || !state.phaseEnteredAt) return banked;
  const live = Date.parse(now) - Date.parse(state.phaseEnteredAt);
  // A device clock can jump backwards — NTP, daylight saving, a user setting
  // it by hand. A negative interval must not eat into the banked total.
  return banked + (Number.isFinite(live) && live > 0 ? live : 0);
}

/**
 * Whether a phase's soft time budget has been spent.
 *
 * Nothing acts on this but the UI, which nudges. The session never advances
 * itself: rushing a beginner is the failure mode PRD §5 exists to avoid.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {string} now - ISO timestamp.
 * @returns {boolean}
 */
export function isOverBudget(steps, state, now) {
  const step = currentStep(steps, state);
  if (!step) return false;
  return phaseElapsedMs(steps, state, step.phase, now) > step.phaseSeconds * 1000;
}

/**
 * Progress through the session, for the indicator.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @returns {{step: number, total: number, phaseIndex: number, phases: number}}
 */
export function progress(steps, state) {
  const phases = new Set(steps.map((s) => s.phase));
  const step = currentStep(steps, state);
  return {
    step: Math.min(state.cursor + 1, steps.length),
    total: steps.length,
    phaseIndex: step ? step.phaseIndex : phases.size,
    phases: phases.size,
  };
}

/**
 * Jump straight to a question.
 *
 * The taster should be able to move around the session the way they would
 * move around a page — go back three questions to change an answer, skip
 * ahead to the phase they are actually on — without stepping through
 * everything in between. Bounded to the session, and a no-op for the step
 * already showing.
 *
 * Banks the phase clock when the jump crosses a phase boundary, exactly as
 * `next` does; a jump is not a way to get free time in a phase.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {number} index - Step to move to.
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function goTo(steps, state, index, now) {
  const target = Math.max(0, Math.min(index, steps.length));
  if (target === state.cursor) return state;

  const leaving = steps[state.cursor];
  const arriving = steps[target];
  const changedPhase = !leaving || !arriving || leaving.phase !== arriving.phase;

  return {
    ...state,
    cursor: target,
    updatedAt: now,
    elapsed: changedPhase && leaving ? accrue(state, leaving.phase, now) : state.elapsed,
    phaseEnteredAt: changedPhase ? now : state.phaseEnteredAt,
  };
}

/**
 * What state each question is in, for the navigation rail.
 *
 * `answered`, `skipped` and `unanswered` are distinct on purpose: a taster
 * looking at the rail needs to tell "I decided I was unsure about this" from
 * "I have not got to this yet", and a single done/not-done flag collapses
 * exactly the distinction PRD §6.1 asks the app to keep.
 *
 * `startsPhase` lets the rail draw one continuous run of markers with a
 * separator where the phases change, rather than four separate groups under
 * four headings. The taster is walking one sequence; the rail should look
 * like one sequence.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @returns {Array<{index: number, phase: string, phaseLabel: string,
 *   short: string, prompt: string, status: string, current: boolean,
 *   startsPhase: boolean}>}
 */
export function questionStates(steps, state) {
  return steps.map((step, index) => {
    const answered = state.answers[step.question.code];
    let status = 'unanswered';
    if (answered?.skipped) status = 'skipped';
    else if (answered?.values.length) status = 'answered';
    return {
      index,
      phase: step.phase,
      phaseLabel: step.phaseLabel,
      short: step.question.short || step.question.prompt,
      prompt: step.question.prompt,
      status,
      current: index === state.cursor,
      startsPhase: index === 0 || steps[index - 1].phase !== step.phase,
    };
  });
}

/**
 * Whether every question has been answered or deliberately skipped.
 *
 * What lets the summary be reachable from anywhere rather than only by
 * walking off the end of the last phase.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @returns {boolean}
 */
export function allAnswered(steps, state) {
  return questionStates(steps, state).every((q) => q.status !== 'unanswered');
}

/**
 * Mark the session complete.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function complete(steps, state, now) {
  const step = currentStep(steps, state);
  return {
    ...state,
    status: STATUS.COMPLETED,
    cursor: steps.length,
    updatedAt: now,
    elapsed: accrue(state, step?.phase, now),
    phaseEnteredAt: null,
  };
}

/**
 * Record the actual wine, after a blind tasting.
 *
 * @param {object} state
 * @param {{grape?: string, origin?: string}} actual
 * @param {string} now - ISO timestamp.
 * @returns {object} The next state.
 */
export function reveal(state, actual, now) {
  return {
    ...state,
    updatedAt: now,
    actual: {
      grape: actual.grape || '',
      origin: actual.origin || '',
    },
  };
}

/**
 * Serialise the session for the sync endpoint.
 *
 * The whole session, every time — not a delta. That is what makes the
 * endpoint idempotent and lets the offline queue retry without bookkeeping.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @returns {object} The request body.
 */
export function toPayload(steps, state) {
  const phaseOf = {};
  steps.forEach((step) => {
    phaseOf[step.question.code] = step.phase;
  });

  return {
    uuid: state.uuid,
    wine_type: state.wineType,
    lexicon_version: state.lexiconVersion,
    status: state.status,
    started_at: state.startedAt,
    client_updated_at: state.updatedAt,
    wine: {
      name: state.wine.name,
      producer: state.wine.producer,
      region: state.wine.region,
      vintage: state.wine.vintage,
      blind: state.wine.blind,
    },
    actual: { grape: state.actual.grape, origin: state.actual.origin },
    responses: Object.entries(state.answers)
      // A question the taster answered and then un-answered (every chip
      // toggled off on a multi-select) is dropped rather than sent empty.
      // The server replaces wholesale, so dropping it here is what removes it
      // there.
      .filter(([, a]) => a.skipped || a.values.length > 0)
      .map(([code, a]) => ({
        question: code,
        phase: phaseOf[code],
        values: a.values,
        skipped: a.skipped,
      })),
  };
}
