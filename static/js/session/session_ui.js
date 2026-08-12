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
 * UI rules from PRD §7, all of which are load-bearing rather than decorative:
 *   - big tap targets, one question per screen
 *   - primary actions at the bottom, in thumb reach
 *   - colour never the only signal: a swatch always sits beside its label
 *   - no scoring, no streaks, nothing that reads as "wrong"
 */

import {
  currentStep,
  isFinished,
  isOverBudget,
  phaseElapsedMs,
  progress,
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
  'flex min-h-14 flex-1 basis-40 cursor-pointer items-center gap-3 rounded-card ' +
  'border px-4 py-3 text-start font-sans';
const CHIP_OFF = 'border-rule bg-paper-raised text-ink';
const CHIP_ON = 'border-accent bg-accent text-accent-contrast';
const BUTTON =
  'min-h-12 rounded-card px-6 py-3 font-sans text-caption cursor-pointer';
const PRIMARY = `${BUTTON} bg-accent text-accent-contrast`;
const SECONDARY = `${BUTTON} border border-rule text-ink-muted`;

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
  const styleGroup = el('div', { class: 'flex flex-wrap gap-3', role: 'radiogroup' });

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
        text: 'The style decides which questions you get asked.',
      }),
    ]),
    styleGroup,
    el('label', { class: 'flex items-center gap-3 font-sans', for: 'blind' }, [
      blind,
      'Tasting blind',
    ]),
    el('details', { class: 'font-sans' }, [
      el('summary', { class: 'cursor-pointer text-caption text-ink-muted', text: 'Name the wine now (optional)' }),
      el('div', { class: 'mt-3 flex flex-col gap-3' }, [
        el('label', { class: 'text-meta tracking-widest uppercase', for: 'wine-producer', text: 'Producer' }),
        producerInput,
        el('label', { class: 'text-meta tracking-widest uppercase', for: 'wine-name', text: 'Wine' }),
        nameInput,
      ]),
    ]),
    el('button', { type: 'submit', class: PRIMARY, text: 'Start tasting' }),
  );
  return form;
}

/**
 * Render one option chip, with its swatch beside — never instead of — its label.
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
      option.swatch
        ? el('span', {
            class: 'size-6 shrink-0 rounded-full border border-rule',
            style: `background:${option.swatch}`,
            'aria-hidden': 'true',
          })
        : null,
      option.label,
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
 * @param {object} options.handlers - {onAnswer, onSkip, onNext, onBack, onPause, onResume}
 * @returns {HTMLElement}
 */
export function renderQuestion({ steps, state, now, handlers }) {
  const step = currentStep(steps, state);
  const { question } = step;
  const answered = state.answers[question.code] || { values: [], skipped: false };
  const p = progress(steps, state);

  const screen = el('section', { class: 'flex min-h-full flex-col gap-6' });

  screen.append(
    el('div', { class: 'flex items-center justify-between gap-4' }, [
      el('p', {
        class: 'font-sans text-meta tracking-eyebrow text-accent uppercase',
        text: `${step.phaseLabel} · ${p.phaseIndex + 1} of ${p.phases}`,
      }),
      el('button', {
        type: 'button',
        class: 'font-sans text-caption text-ink-muted underline cursor-pointer',
        dataset: { action: state.paused ? 'resume' : 'pause' },
        text: state.paused ? 'Resume' : 'Pause',
        onclick: state.paused ? handlers.onResume : handlers.onPause,
      }),
    ]),
    // A meter, not a countdown. It fills, it goes amber when the budget is
    // spent, and it never does anything else — the taster advances, not us.
    el('div', {
      class: 'h-1 w-full rounded-full bg-rule',
      role: 'progressbar',
      'aria-label': 'Time in this phase',
      'aria-valuenow': String(Math.round(phaseElapsedMs(steps, state, step.phase, now) / 1000)),
      'aria-valuemax': String(step.phaseSeconds),
    }, [
      el('div', {
        class: `h-1 rounded-full ${isOverBudget(steps, state, now) ? 'bg-accent' : 'bg-ink-muted'}`,
        style: `width:${Math.min(
          100,
          (phaseElapsedMs(steps, state, step.phase, now) / (step.phaseSeconds * 1000)) * 100,
        )}%`,
      }),
    ]),
  );

  if (state.paused) {
    screen.append(
      el('p', {
        class: 'rounded-card border border-rule bg-paper-raised p-6 text-center text-ink-muted',
        role: 'status',
        text: 'Paused. Nothing is lost — pick it up when you are ready.',
      }),
    );
    return screen;
  }

  screen.append(
    el('h1', { class: 'text-2xl leading-tight font-medium', text: question.prompt }),
  );

  if (question.help) {
    screen.append(
      el('details', { class: 'font-sans text-caption' }, [
        el('summary', { class: 'cursor-pointer text-ink-muted', text: 'Why this matters' }),
        el('p', { class: 'mt-2 text-ink-muted', text: question.help }),
      ]),
    );
  }

  const options = el('div', { class: 'flex flex-wrap gap-3' });
  question.options.forEach((option) => {
    options.append(
      renderChip(option, answered.values.includes(option.code), handlers.onAnswer),
    );
    // A category's descriptors appear once it is chosen, so the first screen
    // is ten chips rather than ninety.
    if (option.children?.length && answered.values.includes(option.code)) {
      const nested = el('div', {
        class: 'flex w-full flex-wrap gap-2 border-s-2 border-rule ps-3',
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

  if (answered.skipped) {
    screen.append(
      el('p', { class: 'font-sans text-caption text-ink-muted', text: 'Marked as unsure.' }),
    );
  }

  // Actions last, so they sit at the bottom of the screen under a thumb.
  screen.append(
    el('div', { class: 'mt-auto flex flex-wrap items-center gap-3' }, [
      state.cursor > 0
        ? el('button', { type: 'button', class: SECONDARY, text: 'Back', onclick: handlers.onBack })
        : null,
      el('button', {
        type: 'button',
        class: SECONDARY,
        dataset: { action: 'skip' },
        text: 'Not sure',
        onclick: handlers.onSkip,
      }),
      el('button', {
        type: 'button',
        class: `${PRIMARY} ms-auto`,
        dataset: { action: 'next' },
        text: p.step === p.total ? 'Finish' : 'Next',
        onclick: handlers.onNext,
      }),
    ]),
  );

  return screen;
}

/**
 * Render the closing summary: everything recorded, then the save.
 *
 * @param {object} options
 * @param {Array<object>} options.steps
 * @param {object} options.state
 * @param {Function} options.labelFor - (questionCode, optionCode) => string
 * @param {object} options.handlers - {onReveal, onSave, onBack}
 * @returns {HTMLElement}
 */
export function renderSummary({ steps, state, labelFor, handlers }) {
  const screen = el('section', { class: 'flex flex-col gap-6' });
  screen.append(
    el('div', {}, [
      el('h1', { class: 'mb-2 text-display font-medium', text: 'What you found' }),
      el('p', { class: 'text-ink-muted', text: 'Everything you recorded, on one screen.' }),
    ]),
  );

  let phase = null;
  const list = el('dl', { class: 'flex flex-col gap-3' });
  steps.forEach((step) => {
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
      el('dd', { class: 'border-b border-rule pb-2' }, [
        el('span', { class: 'block font-sans text-caption text-ink-muted', text: step.question.prompt }),
        el('span', {
          class: answered.skipped ? 'text-ink-muted italic' : '',
          text: answered.skipped
            ? 'Skipped'
            : answered.values.map((v) => labelFor(step.question.code, v)).join(', '),
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
      el('div', { class: 'flex flex-col gap-2 rounded-card border border-rule bg-paper-raised p-4' }, [
        el('label', {
          class: 'font-sans text-meta tracking-widest text-ink-muted uppercase',
          for: 'actual-grape',
          text: 'What was it really?',
        }),
        grape,
      ]),
    );
  }

  screen.append(
    el('div', { class: 'flex flex-wrap items-center gap-3' }, [
      el('button', { type: 'button', class: SECONDARY, text: 'Back', onclick: handlers.onBack }),
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
