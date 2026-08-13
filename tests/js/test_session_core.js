/*
 * tests/js/test_session_core.js — The session state machine.
 *
 * This is where the product's rules live, so this is where most of the
 * client-side testing belongs: no DOM, no storage, no network, nothing to
 * mock. Every case here is a rule from the PRD, and the comments say which.
 */

import { describe, expect, it } from 'vitest';

import {
  STATUS,
  allAnswered,
  answer,
  buildSteps,
  complete,
  createSession,
  currentStep,
  depthRung,
  goTo,
  hasRungMark,
  isFinished,
  isOverBudget,
  next,
  noteSoFar,
  pause,
  phaseElapsedMs,
  previous,
  progress,
  questionStates,
  resume,
  reveal,
  skip,
  toPayload,
} from '../../static/js/session/session_core.js';

const T0 = '2026-03-04T19:30:00.000Z';
const at = (seconds) => new Date(Date.parse(T0) + seconds * 1000).toISOString();

const PAYLOAD = {
  version: '2026.1',
  wine_type: 'still_red',
  phases: [
    {
      code: 'look',
      label: 'Look',
      seconds: 45,
      questions: [
        {
          code: 'clarity',
          prompt: 'Clear or hazy?',
          short: 'Clarity',
          how: 'Hold it against something white.',
          why: 'Haze can mean a fault.',
          control: 'single',
          options: [
            { code: 'clear', label: 'Clear', swatch: '', children: [] },
            { code: 'hazy', label: 'Hazy', swatch: '', children: [] },
          ],
        },
        {
          code: 'colour',
          prompt: 'What colour?',
          short: 'Colour',
          how: 'Tilt the glass.',
          why: '',
          control: 'single',
          options: [{ code: 'ruby', label: 'Ruby', swatch: '#8e1220', children: [] }],
        },
      ],
    },
    {
      code: 'smell',
      label: 'Smell',
      seconds: 90,
      questions: [
        {
          code: 'primary_aromas',
          prompt: 'What can you smell?',
          short: 'Aromas',
          how: 'Short sharp sniffs.',
          why: 'Raw material for the end.',
          control: 'multi',
          options: [
            {
              code: 'citrus',
              label: 'Citrus fruit',
              swatch: '',
              children: [
                { code: 'lemon', label: 'Lemon', swatch: '' },
                { code: 'lime', label: 'Lime', swatch: '' },
              ],
            },
          ],
        },
      ],
    },
  ],
};

const STEPS = buildSteps(PAYLOAD);

/** A Look phase whose second question is the three-rung depth scale. */
const WITH_DEPTH = {
  phases: [
    {
      code: 'look',
      label: 'Look',
      seconds: 45,
      questions: [
        {
          code: 'depth',
          prompt: 'How deep?',
          short: 'Depth',
          control: 'scale',
          options: [
            { code: 'pale', label: 'Pale', children: [] },
            { code: 'medium', label: 'Medium', children: [] },
            { code: 'deep', label: 'Deep', children: [] },
          ],
        },
      ],
    },
  ],
};

function fresh(overrides = {}) {
  return {
    ...createSession({ payload: PAYLOAD, uuid: 'u-1', now: T0 }),
    ...overrides,
  };
}

describe('buildSteps', () => {
  it('flattens phases into one list in running order', () => {
    expect(STEPS.map((s) => s.question.code)).toEqual([
      'clarity',
      'colour',
      'primary_aromas',
    ]);
  });

  it('carries the phase down onto every step', () => {
    expect(STEPS.map((s) => s.phase)).toEqual(['look', 'look', 'smell']);
    expect(STEPS[2].phaseLabel).toBe('Smell');
    expect(STEPS[2].phaseSeconds).toBe(90);
  });

  it('survives a payload with no phases', () => {
    expect(buildSteps({})).toEqual([]);
  });
});

describe('createSession', () => {
  it('records the lexicon version it was started against', () => {
    // Sessions are rendered later with the labels the taster actually saw.
    expect(fresh().lexiconVersion).toBe('2026.1');
  });

  it('starts on the first question, unpaused, with nothing answered', () => {
    const state = fresh();
    expect(state.cursor).toBe(0);
    expect(state.answers).toEqual({});
    expect(state.paused).toBe(false);
    expect(state.status).toBe(STATUS.IN_PROGRESS);
  });

  it('takes the wine details from setup', () => {
    const state = createSession({
      payload: PAYLOAD,
      uuid: 'u-2',
      now: T0,
      wine: { name: 'Barolo', producer: 'Scavino', blind: true },
    });
    expect(state.wine).toMatchObject({ name: 'Barolo', producer: 'Scavino', blind: true });
  });

  it('defaults to a sighted tasting with no wine named', () => {
    expect(fresh().wine).toMatchObject({ name: '', producer: '', blind: false });
  });

  it('produces something structuredClone can store', () => {
    // It goes into IndexedDB on every tap; a class instance or a Date would
    // fail there rather than here.
    expect(() => structuredClone(fresh())).not.toThrow();
  });
});

describe('answer', () => {
  it('records a single-select answer', () => {
    const state = answer(STEPS, fresh(), 'clear', at(5));
    expect(state.answers.clarity.values).toEqual(['clear']);
  });

  it('replaces a single-select answer rather than adding to it', () => {
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = answer(STEPS, state, 'hazy', at(6));
    expect(state.answers.clarity.values).toEqual(['hazy']);
  });

  it('toggles a multi-select on and off', () => {
    // Tapping "lemon" twice means taking it off, not recording it twice.
    let state = fresh({ cursor: 2 });
    state = answer(STEPS, state, 'lemon', at(5));
    state = answer(STEPS, state, 'lime', at(6));
    expect(state.answers.primary_aromas.values).toEqual(['lemon', 'lime']);

    state = answer(STEPS, state, 'lemon', at(7));
    expect(state.answers.primary_aromas.values).toEqual(['lime']);
  });

  it('does not advance', () => {
    // On a multi-select the taster is not finished after the first tap, and a
    // single-select should leave room to change their mind (PRD §7).
    expect(answer(STEPS, fresh(), 'clear', at(5)).cursor).toBe(0);
  });

  it('clears an earlier skip on the same question', () => {
    let state = skip(STEPS, fresh(), at(5));
    state = answer(STEPS, state, 'clear', at(6));
    expect(state.answers.clarity.skipped).toBe(false);
  });

  it('does nothing past the last question', () => {
    const finished = fresh({ cursor: STEPS.length });
    expect(answer(STEPS, finished, 'clear', at(5))).toBe(finished);
  });

  it('does not mutate the state it was given', () => {
    const before = fresh();
    answer(STEPS, before, 'clear', at(5));
    expect(before.answers).toEqual({});
  });
});

describe('skip', () => {
  it('records an explicit skip, not an empty answer', () => {
    // PRD §6.1: "genuinely unsure" is an outcome, not a blank.
    const state = skip(STEPS, fresh(), at(5));
    expect(state.answers.clarity).toEqual({ values: [], skipped: true });
  });

  it('does nothing past the last question', () => {
    const finished = fresh({ cursor: STEPS.length });
    expect(skip(STEPS, finished, at(5))).toBe(finished);
  });
});

describe('next and previous', () => {
  it('moves forward one question', () => {
    expect(next(STEPS, fresh(), at(5)).cursor).toBe(1);
  });

  it('stops at the end rather than running off it', () => {
    const finished = fresh({ cursor: STEPS.length });
    expect(next(STEPS, finished, at(5)).cursor).toBe(STEPS.length);
  });

  it('moves back', () => {
    expect(previous(STEPS, fresh({ cursor: 2 }), at(5)).cursor).toBe(1);
  });

  it('will not move back past the first question', () => {
    expect(previous(STEPS, fresh(), at(5)).cursor).toBe(0);
  });

  it('leaves answers alone when going back', () => {
    // Going back to look at what you put is not the same as erasing it.
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = next(STEPS, state, at(6));
    state = previous(STEPS, state, at(7));
    expect(state.answers.clarity.values).toEqual(['clear']);
  });

  it('banks the phase time when crossing into a new phase', () => {
    let state = next(STEPS, fresh(), at(10)); // clarity -> colour, same phase
    expect(state.elapsed.look).toBeUndefined();

    state = next(STEPS, state, at(30)); // colour -> primary_aromas, new phase
    expect(state.elapsed.look).toBe(30000);
    expect(state.phaseEnteredAt).toBe(at(30));
  });

  it('does not restart the clock within a phase', () => {
    const state = next(STEPS, fresh(), at(10));
    expect(state.phaseEnteredAt).toBe(T0);
  });
});

describe('pause and resume', () => {
  it('banks time so a pause does not inflate the timer', () => {
    // PRD §7: someone will refill your glass mid-session.
    const state = pause(STEPS, fresh(), at(20));
    expect(state.paused).toBe(true);
    expect(state.elapsed.look).toBe(20000);
    expect(state.phaseEnteredAt).toBeNull();
  });

  it('does not accrue time while paused', () => {
    const state = pause(STEPS, fresh(), at(20));
    expect(phaseElapsedMs(STEPS, state, 'look', at(300))).toBe(20000);
  });

  it('restarts the clock on resume without losing what was banked', () => {
    let state = pause(STEPS, fresh(), at(20));
    state = resume(state, at(300));
    expect(state.paused).toBe(false);
    expect(phaseElapsedMs(STEPS, state, 'look', at(310))).toBe(30000);
  });

  it('is idempotent in both directions', () => {
    const paused = pause(STEPS, fresh(), at(20));
    expect(pause(STEPS, paused, at(40))).toBe(paused);
    expect(resume(fresh(), at(40))).toEqual(fresh());
  });
});

describe('phaseElapsedMs', () => {
  it('counts the stretch currently running', () => {
    expect(phaseElapsedMs(STEPS, fresh(), 'look', at(12))).toBe(12000);
  });

  it('ignores a clock that jumped backwards', () => {
    // Device clocks are adjusted by NTP, by the user, and by daylight saving.
    // A negative interval must not subtract from the banked total.
    expect(phaseElapsedMs(STEPS, fresh(), 'look', at(-30))).toBe(0);
  });

  it('is zero for a phase not yet entered', () => {
    expect(phaseElapsedMs(STEPS, fresh(), 'smell', at(12))).toBe(0);
  });
});

describe('isOverBudget', () => {
  it('is false inside the budget', () => {
    expect(isOverBudget(STEPS, fresh(), at(30))).toBe(false);
  });

  it('is true past it', () => {
    expect(isOverBudget(STEPS, fresh(), at(50))).toBe(true);
  });

  it('never advances the session by itself', () => {
    // The timer is a pacing aid, not a countdown — rushing a beginner is the
    // failure mode PRD §5 exists to avoid.
    const state = fresh();
    expect(isOverBudget(STEPS, state, at(500))).toBe(true);
    expect(state.cursor).toBe(0);
  });

  it('is false once the session is finished', () => {
    expect(isOverBudget(STEPS, fresh({ cursor: STEPS.length }), at(500))).toBe(false);
  });
});

describe('progress', () => {
  it('counts steps and phases', () => {
    expect(progress(STEPS, fresh())).toEqual({
      step: 1,
      total: 3,
      phaseIndex: 0,
      phases: 2,
    });
  });

  it('does not exceed the total at the end', () => {
    expect(progress(STEPS, fresh({ cursor: STEPS.length })).step).toBe(3);
  });
});

describe('complete', () => {
  it('marks the session done and banks the last phase', () => {
    const state = complete(STEPS, fresh(), at(40));
    expect(state.status).toBe(STATUS.COMPLETED);
    expect(isFinished(STEPS, state)).toBe(true);
    expect(state.elapsed.look).toBe(40000);
  });
});

describe('reveal', () => {
  it('records the actual wine without touching the guess', () => {
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = reveal(state, { grape: 'Nebbiolo' }, at(10));
    expect(state.actual.grape).toBe('Nebbiolo');
    expect(state.answers.clarity.values).toEqual(['clear']);
  });
});

describe('currentStep and isFinished', () => {
  it('returns null past the end', () => {
    expect(currentStep(STEPS, fresh({ cursor: STEPS.length }))).toBeNull();
  });

  it('reports finished only past the last step', () => {
    expect(isFinished(STEPS, fresh({ cursor: STEPS.length - 1 }))).toBe(false);
    expect(isFinished(STEPS, fresh({ cursor: STEPS.length }))).toBe(true);
  });
});

describe('toPayload', () => {
  it('matches the shape the sync endpoint requires', () => {
    const body = toPayload(STEPS, answer(STEPS, fresh(), 'clear', at(5)));
    expect(body).toMatchObject({
      uuid: 'u-1',
      wine_type: 'still_red',
      lexicon_version: '2026.1',
      status: 'in_progress',
      started_at: T0,
      client_updated_at: at(5),
    });
  });

  it('sends timestamps with a UTC offset, which the server requires', () => {
    const body = toPayload(STEPS, fresh());
    expect(body.client_updated_at).toMatch(/Z$/);
  });

  it('tags each answer with the phase it belongs to', () => {
    let state = answer(STEPS, fresh({ cursor: 2 }), 'lemon', at(5));
    state = answer(STEPS, state, 'clear', at(6)); // still on primary_aromas
    const body = toPayload(STEPS, state);
    expect(body.responses[0]).toMatchObject({
      question: 'primary_aromas',
      phase: 'smell',
    });
  });

  it('sends the whole session every time, not a delta', () => {
    // What makes the endpoint idempotent and lets the queue retry blindly.
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = next(STEPS, state, at(6));
    state = answer(STEPS, state, 'ruby', at(7));
    expect(toPayload(STEPS, state).responses).toHaveLength(2);
  });

  it('includes a skipped question', () => {
    const body = toPayload(STEPS, skip(STEPS, fresh(), at(5)));
    expect(body.responses).toEqual([
      { question: 'clarity', phase: 'look', values: [], skipped: true },
    ]);
  });

  it('drops a question whose answer was toggled back off', () => {
    // The server replaces wholesale, so dropping it here is what removes it
    // there. Sending it empty would store a meaningless blank.
    let state = answer(STEPS, fresh({ cursor: 2 }), 'lemon', at(5));
    state = answer(STEPS, state, 'lemon', at(6));
    expect(toPayload(STEPS, state).responses).toEqual([]);
  });

  it('is JSON-serialisable', () => {
    const body = toPayload(STEPS, answer(STEPS, fresh(), 'clear', at(5)));
    expect(JSON.parse(JSON.stringify(body))).toEqual(body);
  });
});

describe('goTo', () => {
  it('jumps straight to a question', () => {
    // Moving around the session should not mean stepping through answers you
    // were happy with.
    expect(goTo(STEPS, fresh(), 2, at(5)).cursor).toBe(2);
  });

  it('jumps backwards', () => {
    expect(goTo(STEPS, fresh({ cursor: 2 }), 0, at(5)).cursor).toBe(0);
  });

  it('clamps to the session rather than running off either end', () => {
    expect(goTo(STEPS, fresh(), -5, at(5)).cursor).toBe(0);
    expect(goTo(STEPS, fresh(), 99, at(5)).cursor).toBe(STEPS.length);
  });

  it('is a no-op for the step already showing', () => {
    const state = fresh();
    expect(goTo(STEPS, state, 0, at(5))).toBe(state);
  });

  it('banks the phase clock when the jump crosses a phase', () => {
    // A jump is not a way to get free time in a phase.
    const state = goTo(STEPS, fresh(), 2, at(30));
    expect(state.elapsed.look).toBe(30000);
    expect(state.phaseEnteredAt).toBe(at(30));
  });

  it('leaves the clock alone within a phase', () => {
    const state = goTo(STEPS, fresh(), 1, at(30));
    expect(state.elapsed.look).toBeUndefined();
    expect(state.phaseEnteredAt).toBe(T0);
  });

  it('leaves answers alone', () => {
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = goTo(STEPS, state, 2, at(6));
    state = goTo(STEPS, state, 0, at(7));
    expect(state.answers.clarity.values).toEqual(['clear']);
  });

  it('can jump to the end, which is the summary', () => {
    const state = goTo(STEPS, fresh(), STEPS.length, at(5));
    expect(isFinished(STEPS, state)).toBe(true);
  });
});

describe('questionStates', () => {
  it('marks unanswered questions', () => {
    expect(questionStates(STEPS, fresh()).map((q) => q.status)).toEqual([
      'unanswered',
      'unanswered',
      'unanswered',
    ]);
  });

  it('distinguishes answered from skipped from not-yet', () => {
    // "I decided I was unsure" and "I have not got there" are different
    // facts, and a done/not-done flag collapses exactly the distinction
    // PRD §6.1 asks the app to keep.
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = next(STEPS, state, at(6));
    state = skip(STEPS, state, at(7));

    expect(questionStates(STEPS, state).map((q) => q.status)).toEqual([
      'answered',
      'skipped',
      'unanswered',
    ]);
  });

  it('marks exactly one question as current', () => {
    const states = questionStates(STEPS, fresh({ cursor: 1 }));
    expect(states.filter((q) => q.current).map((q) => q.index)).toEqual([1]);
  });

  it('carries the short label the rail renders', () => {
    expect(questionStates(STEPS, fresh()).map((q) => q.short)).toEqual([
      'Clarity',
      'Colour',
      'Aromas',
    ]);
  });

  it('falls back to the prompt when a question has no short label', () => {
    const steps = buildSteps({
      phases: [
        {
          code: 'look',
          label: 'Look',
          seconds: 45,
          questions: [{ code: 'x', prompt: 'A long prompt', control: 'single', options: [] }],
        },
      ],
    });
    expect(questionStates(steps, fresh())[0].short).toBe('A long prompt');
  });

  it('treats a multi-select emptied back out as unanswered', () => {
    let state = answer(STEPS, fresh({ cursor: 2 }), 'lemon', at(5));
    state = answer(STEPS, state, 'lemon', at(6));
    expect(questionStates(STEPS, state)[2].status).toBe('unanswered');
  });

  it('marks the first question of each phase', () => {
    // The rail draws one continuous run with a separator here, rather than
    // four groups under four headings.
    expect(questionStates(STEPS, fresh()).map((q) => q.startsPhase)).toEqual([
      true,
      false,
      true,
    ]);
  });

  it('carries the phase label each marker announces', () => {
    expect(questionStates(STEPS, fresh()).map((q) => q.phaseLabel)).toEqual([
      'Look',
      'Look',
      'Smell',
    ]);
  });
});

describe('allAnswered', () => {
  it('is false while anything is untouched', () => {
    expect(allAnswered(STEPS, fresh())).toBe(false);
  });

  it('is true once every question is answered or skipped', () => {
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = answer(STEPS, next(STEPS, state, at(6)), 'ruby', at(7));
    state = skip(STEPS, next(STEPS, state, at(8)), at(9));
    expect(allAnswered(STEPS, state)).toBe(true);
  });
});

describe('noteSoFar', () => {
  it('is empty before anything is recorded', () => {
    expect(noteSoFar(STEPS, fresh())).toBe('');
  });

  it('composes a sentence from the labels, in step order', () => {
    // The design's centrepiece: the session reads as writing a note rather
    // than filling in a form.
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = answer(STEPS, next(STEPS, state, at(6)), 'ruby', at(7));
    expect(noteSoFar(STEPS, state)).toBe('Clear, ruby');
  });

  it('lower-cases the labels and raises only the first letter', () => {
    // Labels are written to head a chip ("Clear"); dropped mid-sentence
    // unchanged they read as a list of proper nouns.
    let state = answer(STEPS, fresh(), 'clear', at(5));
    state = answer(STEPS, next(STEPS, state, at(6)), 'ruby', at(7));
    expect(noteSoFar(STEPS, state)).not.toContain('Ruby');
  });

  it('follows step order rather than the order they were answered', () => {
    let state = answer(STEPS, fresh({ cursor: 1 }), 'ruby', at(5));
    state = answer(STEPS, goTo(STEPS, state, 0, at(6)), 'clear', at(7));
    expect(noteSoFar(STEPS, state)).toBe('Clear, ruby');
  });

  it('includes every pick of a multi-select', () => {
    const state = answer(
      STEPS,
      answer(STEPS, fresh({ cursor: 2 }), 'lemon', at(5)),
      'lime',
      at(6),
    );
    expect(noteSoFar(STEPS, state)).toBe('Lemon, lime');
  });

  it('resolves a nested descriptor by its own label', () => {
    const state = answer(STEPS, fresh({ cursor: 2 }), 'lemon', at(5));
    expect(noteSoFar(STEPS, state)).toBe('Lemon');
  });

  it('leaves out a skipped question', () => {
    // A note does not say "and I was not sure about the clarity".
    let state = skip(STEPS, fresh(), at(5));
    state = answer(STEPS, next(STEPS, state, at(6)), 'ruby', at(7));
    expect(noteSoFar(STEPS, state)).toBe('Ruby');
  });

  it('leaves out the conclude phase', () => {
    // Look, Smell and Taste are what you observed and read as a note.
    // Conclude is what you deduced, and folding "very good, riesling,
    // guessing" onto the end turns a description into a shopping list.
    const steps = buildSteps({
      phases: [
        {
          code: 'look',
          label: 'Look',
          seconds: 45,
          questions: [
            {
              code: 'clarity',
              prompt: 'Clear?',
              short: 'Clarity',
              control: 'single',
              options: [{ code: 'clear', label: 'Clear', children: [] }],
            },
          ],
        },
        {
          code: 'conclude',
          label: 'Conclude',
          seconds: 90,
          questions: [
            {
              code: 'quality',
              prompt: 'How good?',
              short: 'Quality',
              control: 'scale',
              options: [{ code: 'very_good', label: 'Very good', children: [] }],
            },
          ],
        },
      ],
    });

    let state = answer(steps, fresh(), 'clear', at(5));
    state = answer(steps, next(steps, state, at(6)), 'very_good', at(7));

    expect(noteSoFar(steps, state)).toBe('Clear');
  });
});

describe('hasRungMark', () => {
  /** One step, built the way `buildSteps` builds them. */
  const step = (phase, control) => ({ phase, question: { control } });

  it('marks an observed scale', () => {
    // The ramp is a teaching aid: it shows what pale and deep look like.
    expect(hasRungMark(step('look', 'scale'))).toBe(true);
    expect(hasRungMark(step('taste', 'scale'))).toBe(true);
  });

  it('leaves the Conclude scales unmarked', () => {
    // Quality and confidence are ordered, but they are judgements rather than
    // sensations — a depth ramp beside "faulty → outstanding" would say the
    // wine gets deeper as it gets better.
    expect(hasRungMark(step('conclude', 'scale'))).toBe(false);
  });

  it('leaves categorical questions unmarked wherever they fall', () => {
    expect(hasRungMark(step('look', 'single'))).toBe(false);
    expect(hasRungMark(step('smell', 'multi'))).toBe(false);
    expect(hasRungMark(step('conclude', 'single'))).toBe(false);
  });

  it('says no rather than throwing when there is no step', () => {
    // Called during a render, where a missing step means the session has run
    // off the end — drawing nothing is the right answer, not an exception.
    expect(hasRungMark(undefined)).toBe(false);
    expect(hasRungMark({})).toBe(false);
  });
});

describe('depthRung', () => {
  it('starts on the middle rung', () => {
    // The dots have to be some colour before any depth is recorded.
    expect(depthRung(STEPS, fresh())).toBe(2);
  });

  it('takes the rung the taster recorded', () => {
    // "Once the taster records colour depth, pass that swatch colour so the
    // row stains itself the colour of the wine" — ProgressDots.
    const steps = buildSteps(WITH_DEPTH);
    let state = fresh();
    state = { ...state, answers: { depth: { values: ['deep'], skipped: false } } };
    expect(depthRung(steps, state)).toBe(3);
  });

  it('reads the palest rung as one', () => {
    const steps = buildSteps(WITH_DEPTH);
    const state = { ...fresh(), answers: { depth: { values: ['pale'], skipped: false } } };
    expect(depthRung(steps, state)).toBe(1);
  });

  it('falls back to the middle when the question was skipped', () => {
    const steps = buildSteps(WITH_DEPTH);
    const state = { ...fresh(), answers: { depth: { values: [], skipped: true } } };
    expect(depthRung(steps, state)).toBe(2);
  });

  it('ignores a scale question outside the opening phase', () => {
    // The depth question is the first scale question in the first phase; a
    // scale later on is acidity or tannin and says nothing about colour.
    const steps = buildSteps({
      phases: [
        {
          code: 'look',
          label: 'Look',
          seconds: 45,
          questions: [
            { code: 'clarity', prompt: 'Clear?', short: 'Clarity', control: 'single', options: [] },
          ],
        },
        {
          code: 'taste',
          label: 'Taste',
          seconds: 150,
          questions: [
            {
              code: 'acidity',
              prompt: 'Acidity?',
              short: 'Acidity',
              control: 'scale',
              options: [
                { code: 'low', label: 'Low', children: [] },
                { code: 'high', label: 'High', children: [] },
              ],
            },
          ],
        },
      ],
    });
    const state = { ...fresh(), answers: { acidity: { values: ['high'], skipped: false } } };
    expect(depthRung(steps, state)).toBe(2);
  });

  it('caps at three however many rungs the scale has', () => {
    const steps = buildSteps({
      phases: [
        {
          code: 'look',
          label: 'Look',
          seconds: 45,
          questions: [
            {
              code: 'depth',
              prompt: 'Depth?',
              short: 'Depth',
              control: 'scale',
              options: ['a', 'b', 'c', 'd', 'e'].map((c) => ({ code: c, label: c, children: [] })),
            },
          ],
        },
      ],
    });
    const state = { ...fresh(), answers: { depth: { values: ['e'], skipped: false } } };
    expect(depthRung(steps, state)).toBe(3);
  });
});
