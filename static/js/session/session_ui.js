/*
 * static/js/session/session_ui.js — Drawing the session, and nothing else.
 *
 * Every decision about what the session *is* lives in session_core.js. This
 * module renders whatever state it is handed and turns taps back into calls.
 * Keeping it that thin is what lets the rules be tested without a DOM, and
 * what keeps a re-render cheap enough to sit inside PRD §8's 200ms budget.
 *
 * Rendering is full-replace rather than diffed. At one question per screen
 * that is a handful of nodes, and a diffing layer would be more code than the
 * thing it optimises.
 *
 * Three things this screen is built around:
 *
 *   1. **It teaches.** `how` sits under the prompt, always visible — not
 *      behind a toggle. Every option carries its own guidance, because the
 *      difference between medium and high acidity is the entire difficulty
 *      and a label alone teaches nobody.
 *   2. **You can see where you are.** One rail of every question in the
 *      session, filling in as they are answered, tappable, with a hairline
 *      where the phase changes. Back and Next name where they go rather than
 *      saying "back" and "next".
 *   3. **It never scores you.** No streaks, no right answers, nothing that
 *      reads as wrong (PRD §7).
 *
 * Other rules from §7 that are load-bearing rather than decorative: big tap
 * targets, one question per screen, primary actions in thumb reach, and
 * colour never the only signal — a swatch always sits beside its label.
 */

import {
  allAnswered,
  currentStep,
  isFinished,
  isOverBudget,
  phaseElapsedMs,
  progress,
  questionStates,
} from './session_core.js';

/**
 * Create an element with attributes and children in one call.
 *
 * @param {string} tag
 * @param {object} [attrs] - Properties; `class`, `dataset` and `on*` handled.
 * @param {Array<Node|string>} [children]
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value === null || value === undefined || value === false) return;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (key === 'text') node.textContent = value;
    else node.setAttribute(key, value === true ? '' : String(value));
  });
  children.filter(Boolean).forEach((child) => {
    node.append(child instanceof Node ? child : document.createTextNode(child));
  });
  return node;
}

// Layout only. Colour lives in CHIP_OFF / CHIP_ON, and the two sets are
// mutually exclusive rather than layered: putting `bg-accent` after
// `bg-paper-raised` in a class string does NOT make it win, because the
// cascade goes by stylesheet order, not by the order classes are written.
// Composing them was how the selected chip came out dark-on-dark.
const CHIP =
  'flex min-h-14 w-full cursor-pointer flex-col items-start gap-1 rounded-card ' +
  'border px-4 py-3 text-start font-sans';
const CHIP_OFF = 'border-rule bg-paper-raised text-ink';
const CHIP_ON = 'border-accent bg-accent text-accent-contrast';
const BUTTON =
  'min-h-12 rounded-card px-5 py-3 font-sans text-caption cursor-pointer';
const PRIMARY = `${BUTTON} bg-accent text-accent-contrast`;
const SECONDARY = `${BUTTON} border border-rule text-ink-muted`;

/** Marker styles for the progress rail, by answer state. */
const MARKER = {
  answered: 'bg-accent',
  skipped: 'border border-dashed border-ink-muted',
  unanswered: 'border border-rule',
};

/**
 * Render the setup screen: wine style, and optionally what the wine is.
 *
 * @param {object} options
 * @param {Array<{value: string, label: string}>} options.wineTypes
 * @param {(wineType: string, wine: object) => void} options.onStart
 * @returns {HTMLElement}
 */
export function renderSetup({ wineTypes, onStart }) {
  let chosen = wineTypes[0]?.value;

  const form = el('form', { class: 'flex flex-col gap-6' });
  const styleGroup = el('div', { class: 'flex flex-col gap-3', role: 'radiogroup' });

  const buttons = wineTypes.map((type) =>
    el(
      'button',
      {
        type: 'button',
        class: `${CHIP} ${type.value === chosen ? CHIP_ON : CHIP_OFF}`,
        role: 'radio',
        'aria-checked': type.value === chosen ? 'true' : 'false',
        dataset: { value: type.value },
        onclick: () => {
          chosen = type.value;
          buttons.forEach((b) => {
            const on = b.dataset.value === chosen;
            b.className = `${CHIP} ${on ? CHIP_ON : CHIP_OFF}`;
            b.setAttribute('aria-checked', on ? 'true' : 'false');
          });
        },
      },
      [type.label],
    ),
  );
  buttons.forEach((b) => styleGroup.append(b));

  const blind = el('input', {
    type: 'checkbox',
    id: 'blind',
    class: 'size-5',
    checked: true,
  });
  const nameInput = el('input', {
    type: 'text',
    id: 'wine-name',
    class: 'rounded-card border border-rule bg-paper-raised px-4 py-3 font-sans',
    placeholder: 'Optional',
    autocomplete: 'off',
  });
  const producerInput = el('input', {
    type: 'text',
    id: 'wine-producer',
    class: 'rounded-card border border-rule bg-paper-raised px-4 py-3 font-sans',
    placeholder: 'Optional',
    autocomplete: 'off',
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    onStart(chosen, {
      name: nameInput.value.trim(),
      producer: producerInput.value.trim(),
      blind: blind.checked,
    });
  });

  form.append(
    el('div', {}, [
      el('h1', { class: 'mb-2 text-display font-medium', text: 'What are you tasting?' }),
      el('p', {
        class: 'text-ink-muted',
        text: 'The style decides which questions you get — a Riesling gets no tannin question.',
      }),
    ]),
    styleGroup,
    el('label', { class: 'flex items-center gap-3 font-sans', for: 'blind' }, [
      blind,
      'Tasting blind',
    ]),
    el('details', { class: 'font-sans' }, [
      el('summary', {
        class: 'cursor-pointer text-caption text-ink-muted',
        text: 'Name the wine now (optional)',
      }),
      el('div', { class: 'mt-3 flex flex-col gap-3' }, [
        el('label', {
          class: 'text-meta tracking-widest uppercase',
          for: 'wine-producer',
          text: 'Producer',
        }),
        producerInput,
        el('label', {
          class: 'text-meta tracking-widest uppercase',
          for: 'wine-name',
          text: 'Wine',
        }),
        nameInput,
      ]),
    ]),
    el('button', { type: 'submit', class: PRIMARY, text: 'Start tasting' }),
  );
  return form;
}

/**
 * Render the warning shown when local storage would not open.
 *
 * The session still runs and still syncs; what it loses is surviving a
 * reload. Saying so plainly beats both alternatives: refusing to start, and
 * letting someone taste for ten minutes before discovering it on a refresh.
 *
 * @returns {HTMLElement}
 */
export function renderStorageWarning() {
  return el('p', {
    class:
      'mb-4 rounded-card border border-accent bg-paper-raised px-4 py-3 font-sans text-caption',
    role: 'status',
    dataset: { role: 'storage-warning' },
    text:
      'This browser will not let us save locally, so the tasting is held in ' +
      'memory only — it will sync as you go, but do not reload the page. ' +
      'Private browsing is the usual cause.',
  });
}

/**
 * Render the progress rail: every question in the session, in one run.
 *
 * One marker per question, start to finish, filling in as they are answered —
 * not four groups under four headings. The taster is walking a single
 * sequence, and splitting the rail by phase made them count twice to work out
 * where they were. Phase changes are a thin separator; the phase itself is
 * named under the actions, where the question count already sits.
 *
 * Answered and not-yet are the two marks a live session produces. The dashed
 * `skipped` mark is still rendered because sessions recorded before the
 * "Not sure" button was removed carry it, and a note that silently loses a
 * line is worse than one with an unfamiliar mark.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {(index: number) => void} onJump
 * @returns {HTMLElement}
 */
export function renderProgressRail(steps, state, onJump) {
  const rail = el('nav', {
    class: 'flex flex-wrap items-center gap-y-1',
    'aria-label': 'All questions',
  });

  questionStates(steps, state).forEach((question) => {
    // A hairline where the phase changes. Decorative, and hidden from the
    // accessibility tree — each marker names its own phase instead, which
    // carries the grouping without depending on seeing the gap.
    if (question.startsPhase && question.index > 0) {
      rail.append(
        el('span', { class: 'mx-1 h-3 w-px bg-rule', 'aria-hidden': 'true' }),
      );
    }

    rail.append(
      el(
        'button',
        {
          type: 'button',
          // Small mark, larger hit area: the padding is the tap target.
          // Kept tight so twenty markers plus their separators fit one line
          // at the reading measure — a rail that wraps to a stranded second
          // row stops reading as one sequence, which is the whole point.
          class: 'cursor-pointer p-1',
          'aria-label': `${question.phaseLabel}, ${question.short}: ${question.status}`,
          'aria-current': question.current ? 'step' : null,
          title: `${question.short} — ${question.status}`,
          dataset: { index: String(question.index), status: question.status },
          onclick: () => onJump(question.index),
        },
        [
          el('span', {
            class:
              `block size-3 rounded-full ${MARKER[question.status]} ` +
              (question.current ? 'ring-2 ring-accent ring-offset-2 ring-offset-paper' : ''),
          }),
        ],
      ),
    );
  });

  return rail;
}

/**
 * Render one option, with the guidance that says how to know it is this one.
 *
 * @param {object} option
 * @param {boolean} selected
 * @param {(code: string) => void} onPick
 * @returns {HTMLElement}
 */
function renderChip(option, selected, onPick) {
  return el(
    'button',
    {
      type: 'button',
      class: `${CHIP} ${selected ? CHIP_ON : CHIP_OFF}`,
      'aria-pressed': selected ? 'true' : 'false',
      dataset: { code: option.code },
      onclick: () => onPick(option.code),
    },
    [
      el('span', { class: 'flex items-center gap-3' }, [
        option.swatch
          ? el('span', {
              class: 'size-5 shrink-0 rounded-full border border-rule',
              style: `background:${option.swatch}`,
              'aria-hidden': 'true',
            })
          : null,
        el('span', { text: option.label }),
      ]),
      option.guidance
        ? el('span', {
            // Muted against the card, but inheriting the contrast colour when
            // the chip is selected — otherwise the guidance vanishes at the
            // moment the taster has just chosen it.
            class: selected ? 'text-caption opacity-90' : 'text-caption text-ink-muted',
            text: option.guidance,
          })
        : null,
    ],
  );
}

/**
 * Render the current question.
 *
 * @param {object} options
 * @param {Array<object>} options.steps
 * @param {object} options.state
 * @param {string} options.now - ISO timestamp.
 * @param {object} options.handlers
 * @returns {HTMLElement}
 */
export function renderQuestion({ steps, state, now, handlers }) {
  const step = currentStep(steps, state);
  const { question } = step;
  const answered = state.answers[question.code] || { values: [], skipped: false };
  const p = progress(steps, state);
  const questions = questionStates(steps, state);
  const elapsed = phaseElapsedMs(steps, state, step.phase, now);

  const screen = el('section', { class: 'flex min-h-full flex-col gap-5' });

  screen.append(
    // Where you are, above the rail rather than under the actions: the
    // caption labels the markers, so the two are one block and read
    // top-down — phase and position, then the markers, then the question.
    // Grouped in their own column so the screen's gap does not push them
    // apart into unrelated things.
    el('div', { class: 'flex flex-col gap-2' }, [
      el('p', {
        class: 'font-sans text-meta tracking-widest text-ink-muted uppercase',
        dataset: { role: 'position' },
        text: `${step.phaseLabel} · question ${p.step} of ${p.total}`,
      }),
      el('div', { class: 'flex items-start justify-between gap-4' }, [
        renderProgressRail(steps, state, handlers.onJump),
        el('button', {
          type: 'button',
          class: 'cursor-pointer font-sans text-caption text-ink-muted underline',
          dataset: { action: state.paused ? 'resume' : 'pause' },
          text: state.paused ? 'Resume' : 'Pause',
          onclick: state.paused ? handlers.onResume : handlers.onPause,
        }),
      ]),
    ]),
    // A meter, not a countdown. It fills, it goes accent-coloured when the
    // budget is spent, and it never does anything else — the taster advances,
    // not us.
    el(
      'div',
      {
        class: 'h-1 w-full rounded-full bg-rule',
        role: 'progressbar',
        'aria-label': 'Time in this phase',
        'aria-valuenow': String(Math.round(elapsed / 1000)),
        'aria-valuemax': String(step.phaseSeconds),
      },
      [
        el('div', {
          class: `h-1 rounded-full ${
            isOverBudget(steps, state, now) ? 'bg-accent' : 'bg-ink-muted'
          }`,
          style: `width:${Math.min(100, (elapsed / (step.phaseSeconds * 1000)) * 100)}%`,
        }),
      ],
    ),
  );

  if (state.paused) {
    screen.append(
      el('p', {
        class:
          'rounded-card border border-rule bg-paper-raised p-6 text-center text-ink-muted',
        role: 'status',
        text: 'Paused. Nothing is lost — pick it up when you are ready.',
      }),
    );
    return screen;
  }

  screen.append(
    el('h1', { class: 'text-2xl leading-tight font-medium', text: question.prompt }),
  );

  // The instruction, in the open. This is what makes the app a tool rather
  // than a quiz, so it does not go behind a toggle.
  if (question.how) {
    screen.append(
      el('p', {
        class:
          'rounded-card border-s-2 border-accent bg-paper-raised px-4 py-3 font-sans text-caption',
        dataset: { role: 'how-to-tell' },
        text: question.how,
      }),
    );
  }

  const options = el('div', { class: 'flex flex-col gap-2' });
  question.options.forEach((option) => {
    options.append(
      renderChip(option, answered.values.includes(option.code), handlers.onAnswer),
    );
    // A category's descriptors appear once it is chosen, so the first screen
    // is a dozen chips rather than ninety.
    if (option.children?.length && answered.values.includes(option.code)) {
      const nested = el('div', {
        class: 'flex w-full flex-col gap-2 border-s-2 border-rule ps-3',
      });
      option.children.forEach((child) => {
        nested.append(
          renderChip(child, answered.values.includes(child.code), handlers.onAnswer),
        );
      });
      options.append(nested);
    }
  });
  screen.append(options);

  if (question.why) {
    screen.append(
      el('details', { class: 'font-sans text-caption' }, [
        el('summary', {
          class: 'cursor-pointer text-ink-muted',
          text: 'Why this matters',
        }),
        el('p', { class: 'mt-2 text-ink-muted', text: question.why }),
      ]),
    );
  }

  // Actions last, so they sit at the bottom of the screen under a thumb. Both
  // name their destination: "← Colour" tells you what you are about to see,
  // where "Back" only tells you which way you are going.
  const back = questions[state.cursor - 1];
  const forward = questions[state.cursor + 1];

  screen.append(
    el('div', { class: 'mt-auto flex flex-col gap-3' }, [
      // Always reachable. It used to appear only once every question was
      // answered, which was fine while "Not sure" existed to dispose of the
      // ones you could not answer. Without it, a single unanswerable question
      // would hide the way to the summary for the rest of the session.
      el('button', {
        type: 'button',
        class: 'cursor-pointer text-start font-sans text-caption underline',
        dataset: { action: 'review' },
        text: allAnswered(steps, state)
          ? 'Everything is answered — review and save'
          : 'Review and save',
        onclick: handlers.onReview,
      }),
      el('div', { class: 'flex flex-wrap items-center gap-3' }, [
        back
          ? el('button', {
              type: 'button',
              class: SECONDARY,
              dataset: { action: 'back' },
              text: `← ${back.short}`,
              onclick: handlers.onBack,
            })
          : null,
        el('button', {
          type: 'button',
          class: `${PRIMARY} ms-auto`,
          dataset: { action: 'next' },
          text: forward ? `${forward.short} →` : 'Finish',
          onclick: handlers.onNext,
        }),
      ]),
    ]),
  );

  return screen;
}

/**
 * Render what the descriptors mean.
 *
 * This is the half of the method the app owes the taster rather than demands
 * from them: they recorded brioche and butter, and this is where they are
 * told that means lees ageing and malolactic conversion.
 *
 * @param {{groups: Array<object>, conclusions: Array<object>}} reading
 * @returns {HTMLElement|null}
 */
export function renderReading(reading) {
  if (!reading.groups.length && !reading.conclusions.length) return null;

  const section = el('section', {
    class: 'flex flex-col gap-4 rounded-card border border-rule bg-paper-raised p-4',
    dataset: { role: 'reading' },
  });
  section.append(
    el('h2', {
      class: 'font-sans text-meta tracking-eyebrow text-accent uppercase',
      text: 'What that tells you',
    }),
  );

  reading.groups.forEach((group) => {
    section.append(
      el('div', { dataset: { origin: group.origin } }, [
        el('p', {
          class: 'font-sans text-meta tracking-widest text-ink-muted uppercase',
          text: group.label,
        }),
        el('p', { text: group.descriptors.join(', ') }),
      ]),
    );
  });

  reading.conclusions.forEach((conclusion) => {
    section.append(
      el('div', { class: 'border-t border-rule pt-3', dataset: { inference: conclusion.code } }, [
        el('p', { class: 'font-medium', text: conclusion.label }),
        el('p', {
          class: 'font-sans text-caption text-ink-muted',
          // Shows its working. "Because you found butter and cream" is the
          // teaching half; the label on its own is one more thing to learn by
          // rote.
          text: `Because you found ${conclusion.evidence.join(', ')}.`,
        }),
        el('p', { class: 'mt-1 text-caption', text: conclusion.explanation }),
      ]),
    );
  });

  return section;
}

/**
 * Render the closing summary: what you found, what it means, then the save.
 *
 * @param {object} options
 * @param {Array<object>} options.steps
 * @param {object} options.state
 * @param {object} options.reading - From session_inference.interpret.
 * @param {Function} options.labelFor - (questionCode, optionCode) => string
 * @param {object} options.handlers
 * @returns {HTMLElement}
 */
export function renderSummary({ steps, state, reading, labelFor, handlers }) {
  const screen = el('section', { class: 'flex flex-col gap-6' });
  screen.append(
    el('div', {}, [
      el('h1', { class: 'mb-2 text-display font-medium', text: 'What you found' }),
      el('p', {
        class: 'text-ink-muted',
        text: 'Everything you recorded, and what it points at.',
      }),
    ]),
  );

  const readingBlock = renderReading(reading);
  if (readingBlock) screen.append(readingBlock);

  let phase = null;
  const list = el('dl', { class: 'flex flex-col gap-3' });
  steps.forEach((step, index) => {
    const answered = state.answers[step.question.code];
    if (!answered) return;
    if (step.phase !== phase) {
      phase = step.phase;
      list.append(
        el('dt', {
          class: 'mt-3 font-sans text-meta tracking-eyebrow text-accent uppercase',
          text: step.phaseLabel,
        }),
      );
    }
    list.append(
      el('dd', { class: 'flex items-baseline gap-3 border-b border-rule pb-2' }, [
        el('span', {
          class: 'flex-1 font-sans text-caption text-ink-muted',
          text: step.question.short || step.question.prompt,
        }),
        el('span', {
          class: answered.skipped ? 'text-ink-muted italic' : '',
          text: answered.skipped
            ? 'Skipped'
            : answered.values.map((v) => labelFor(step.question.code, v)).join(', '),
        }),
        // Every line is a way back to the question that produced it. Reaching
        // an answer you want to change should not mean walking backwards
        // through the ones you were happy with.
        el('button', {
          type: 'button',
          class: 'cursor-pointer font-sans text-caption text-ink-muted underline',
          dataset: { action: 'edit', question: step.question.code },
          'aria-label': `Change your answer to: ${step.question.prompt}`,
          text: 'Change',
          onclick: () => handlers.onJump(index),
        }),
      ]),
    );
  });
  screen.append(list);

  if (state.wine.blind) {
    const grape = el('input', {
      type: 'text',
      id: 'actual-grape',
      class: 'rounded-card border border-rule bg-paper-raised px-4 py-3 font-sans',
      placeholder: 'Optional',
      value: state.actual.grape,
      oninput: (e) => handlers.onReveal({ grape: e.target.value }),
    });
    screen.append(
      el(
        'div',
        {
          class:
            'flex flex-col gap-2 rounded-card border border-rule bg-paper-raised p-4',
        },
        [
          el('label', {
            class: 'font-sans text-meta tracking-widest text-ink-muted uppercase',
            for: 'actual-grape',
            text: 'What was it really?',
          }),
          grape,
        ],
      ),
    );
  }

  screen.append(
    el('div', { class: 'flex flex-wrap items-center gap-3' }, [
      el('button', {
        type: 'button',
        class: SECONDARY,
        dataset: { action: 'back' },
        text: '← Back to the questions',
        onclick: handlers.onBack,
      }),
      el('button', {
        type: 'button',
        class: `${PRIMARY} ms-auto`,
        dataset: { action: 'save' },
        text: 'Save to journal',
        onclick: handlers.onSave,
      }),
    ]),
  );
  return screen;
}

/**
 * Replace the mount's contents with the screen the state calls for.
 *
 * @param {HTMLElement} mount
 * @param {Node} screen
 */
export function paint(mount, screen) {
  mount.replaceChildren(screen);
}

/**
 * Pick the screen for a state.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @returns {'question'|'summary'}
 */
export function screenFor(steps, state) {
  return isFinished(steps, state) ? 'summary' : 'question';
}
