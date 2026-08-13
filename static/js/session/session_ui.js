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
 * The layout follows the Claude Design project "Wine Tasting Guide Design
 * Directions", ui_kits/tasting-app. Four things carry that design, and each
 * is doing a job:
 *
 *   1. **The note card leads.** "Your note so far" shows the sentence being
 *      composed — "Clear, medium, ruby…" — with the progress markers and the
 *      count inside it. The session reads as writing a note rather than
 *      filling in a form, and the thing being built is never off screen.
 *   2. **The wine themes the session.** The style chosen at setup sets the
 *      accent, the paper tint, the action bar and the depth ramp, so a red
 *      session looks like red wine. Set with data-wine on the mount.
 *   3. **It teaches.** The hint sits under the question, in the open. Every
 *      option carries its own guidance, because the difference between medium
 *      and high acidity is the entire difficulty and a label alone teaches
 *      nobody. "Why it matters" is a sheet, one tap away.
 *   4. **It never scores you.** No streaks, no right answers, nothing that
 *      reads as wrong (PRD §7).
 *
 * Other rules from §7 that are load-bearing rather than decorative: big tap
 * targets (76px option rows, 52px controls), one question per screen, the
 * action bar pinned in thumb reach, and colour never the only signal — a
 * swatch always sits beside its label.
 */

import {
  allAnswered,
  currentStep,
  depthRung,
  hasRungMark,
  isFinished,
  isOverBudget,
  noteSoFar,
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

/**
 * Build an inline SVG icon from a path.
 *
 * @param {string} d - Path data.
 * @param {object} [options]
 * @returns {SVGElement}
 */
function icon(d, { size = 20, stroke = 'currentColor', width = 1.6 } = {}) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', stroke);
  svg.setAttribute('stroke-width', String(width));
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('shrink-0');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', d);
  svg.append(path);
  return svg;
}

const CHEVRON_LEFT = 'M15 6l-6 6 6 6';
const LIGHTBULB = 'M9 18h6M10 21h4M12 3a6 6 0 0 1 4 10.5V16H8v-2.5A6 6 0 0 1 12 3z';

// Layout only. Colour lives in the ON/OFF pairs, and the two sets are
// mutually exclusive rather than layered: putting `border-accent` after
// `border-rule` in a class string does NOT make it win, because the cascade
// goes by stylesheet order, not by the order classes are written. Composing
// them was how the selected chip once came out dark-on-dark.
const OPTION =
  'flex w-full min-h-19 cursor-pointer items-center gap-4 rounded-card ' +
  'border px-4 py-4 text-start';
const OPTION_OFF = 'border-rule bg-paper-sunken';
const OPTION_ON = 'border-accent bg-paper-raised';

const CONTROL =
  'min-h-13 cursor-pointer rounded-control px-5 font-sans text-control font-medium';
const PRIMARY = `${CONTROL} flex-1 bg-accent text-accent-contrast`;
const SECONDARY = `${CONTROL} border border-rule-strong text-ink`;

const META = 'font-mono text-meta tracking-meta uppercase text-ink-faint';
const META_LG = 'font-mono text-meta-lg tracking-meta uppercase';

/**
 * Marker styles for the progress rail, by answer state.
 *
 * The wine's depth ramp, not the accent — "accent appears only on the note
 * rule, current dot, hint icon and advance button" (guidelines/
 * colors-accent-use), and the dots guideline puts them on depth. The rung is
 * substituted per render, so the row stains itself the colour the taster
 * actually recorded.
 */
const marker = (status, rung) =>
  ({
    answered: `bg-depth-${rung}`,
    skipped: 'border border-dashed border-ink-disabled',
    unanswered: 'border border-rule-strong',
  })[status];

/**
 * Render the setup screen: wine style, and optionally what the wine is.
 *
 * Each style previews its own theme — the swatch is that wine's mid depth —
 * so the choice shows what the session will look like, not just what it is
 * called.
 *
 * @param {object} options
 * @param {Array<{value: string, label: string}>} options.wineTypes
 * @param {(wineType: string, wine: object) => void} options.onStart
 * @returns {HTMLElement}
 */
export function renderSetup({ wineTypes, onStart }) {
  let chosen = null;

  const form = el('form', { class: 'flex flex-1 flex-col gap-5' });
  const styleGroup = el('div', { class: 'flex flex-col gap-2.5', role: 'radiogroup' });
  const start = el('button', {
    type: 'submit',
    class: `${PRIMARY} w-full`,
    text: 'Start tasting',
    disabled: true,
  });
  start.classList.add('opacity-35');

  const buttons = wineTypes.map((type) =>
    el(
      'button',
      {
        type: 'button',
        class: `${OPTION} ${OPTION_OFF}`,
        role: 'radio',
        'aria-checked': 'false',
        // Themes the row itself, so the swatch is the wine's own colour.
        dataset: { value: type.value, wine: type.value },
        onclick: () => {
          chosen = type.value;
          buttons.forEach((b) => {
            const on = b.dataset.value === chosen;
            b.className = `${OPTION} ${on ? OPTION_ON : OPTION_OFF}`;
            b.setAttribute('aria-checked', on ? 'true' : 'false');
          });
          form.dataset.wine = chosen;
          start.disabled = false;
          start.classList.remove('opacity-35');
        },
      },
      [
        el('span', {
          class: 'size-8 shrink-0 rounded-full border border-rule-strong bg-depth-2',
          'aria-hidden': 'true',
        }),
        el('span', { class: 'font-serif text-answer', text: type.label }),
      ],
    ),
  );
  buttons.forEach((b) => styleGroup.append(b));

  const blind = el('input', {
    type: 'checkbox',
    id: 'blind',
    class: 'size-5.5 accent-accent',
    checked: true,
  });
  const nameInput = el('input', {
    type: 'text',
    id: 'wine-name',
    class:
      'rounded-control border border-rule bg-paper-raised px-4 py-3 font-sans text-body',
    placeholder: 'Optional',
    autocomplete: 'off',
  });
  const producerInput = el('input', {
    type: 'text',
    id: 'wine-producer',
    class:
      'rounded-control border border-rule bg-paper-raised px-4 py-3 font-sans text-body',
    placeholder: 'Optional',
    autocomplete: 'off',
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!chosen) return;
    onStart(chosen, {
      name: nameInput.value.trim(),
      producer: producerInput.value.trim(),
      blind: blind.checked,
    });
  });

  form.append(
    el('div', { class: 'flex flex-col gap-2' }, [
      el('span', { class: META, text: 'New tasting' }),
      el('h1', {
        class: 'font-serif text-question font-normal',
        text: 'What are you tasting?',
      }),
      el('p', {
        class: 'font-sans text-body text-ink-muted',
        text: 'The style decides which questions you get — and how the session looks.',
      }),
    ]),
    styleGroup,
    el('label', { class: 'flex items-center gap-3 font-sans text-body', for: 'blind' }, [
      blind,
      'Tasting blind',
    ]),
    el('details', { class: 'font-sans' }, [
      el('summary', {
        class: 'cursor-pointer text-caption text-ink-muted',
        text: 'Name the wine now (optional)',
      }),
      el('div', { class: 'mt-3 flex flex-col gap-3' }, [
        el('label', { class: META, for: 'wine-producer', text: 'Producer' }),
        producerInput,
        el('label', { class: META, for: 'wine-name', text: 'Wine' }),
        nameInput,
      ]),
    ]),
    el('div', { class: 'mt-auto pt-4' }, [start]),
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
      'mb-4 rounded-card border border-rule-strong bg-paper-raised px-4 py-3 font-sans text-fact',
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
 * One marker per question, start to finish, filling in as they are answered.
 * The taster is walking a single sequence, so the rail is a single sequence —
 * splitting it by phase made them count twice to work out where they were.
 * Phase changes are a hairline.
 *
 * Lives inside the note card, beside the count, because it is about the note
 * being built rather than about the screen.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {(index: number) => void} onJump
 * @returns {HTMLElement}
 */
export function renderProgressRail(steps, state, onJump) {
  const rung = depthRung(steps, state);
  const rail = el('nav', {
    class: 'flex flex-1 flex-wrap items-center gap-y-1',
    'aria-label': 'All questions',
  });

  questionStates(steps, state).forEach((question) => {
    // A hairline where the phase changes. Decorative, and hidden from the
    // accessibility tree — each marker names its own phase instead, which
    // carries the grouping without depending on seeing the gap.
    if (question.startsPhase && question.index > 0) {
      rail.append(
        el('span', { class: 'mx-1 h-2.5 w-px bg-rule-strong', 'aria-hidden': 'true' }),
      );
    }

    rail.append(
      el(
        'button',
        {
          type: 'button',
          // Small mark, larger hit area: the padding is the tap target.
          class: 'cursor-pointer px-0.5 py-1',
          'aria-label': `${question.phaseLabel}, ${question.short}: ${question.status}`,
          'aria-current': question.current ? 'step' : null,
          title: `${question.short} — ${question.status}`,
          dataset: { index: String(question.index), status: question.status },
          onclick: () => onJump(question.index),
        },
        [
          el('span', {
            class:
              `block size-2.5 rounded-full ${marker(question.status, rung)} ` +
              (question.current
                ? `ring-2 ring-depth-${rung} ring-offset-1 ring-offset-paper-raised`
                : ''),
          }),
        ],
      ),
    );
  });

  return rail;
}

/**
 * Render the note card: the sentence being composed, and how far in you are.
 *
 * The accent rule along its top is the wine's own colour, so the card is the
 * one place the style being tasted is always visible.
 *
 * @param {Array<object>} steps
 * @param {object} state
 * @param {(index: number) => void} onJump
 * @returns {HTMLElement}
 */
export function renderNoteCard(steps, state, onJump, onExpand) {
  const note = noteSoFar(steps, state);
  const p = progress(steps, state);
  const answered = questionStates(steps, state).filter(
    (q) => q.status !== 'unanswered',
  ).length;
  const pad = (n) => String(n).padStart(2, '0');

  return el(
    'section',
    {
      class:
        'flex flex-col gap-2.5 rounded-card border border-rule border-t-3 ' +
        'border-t-accent bg-paper-raised px-4 py-3.5',
      dataset: { role: 'note-card' },
      'aria-label': 'Your note so far',
    },
    [
      el('div', { class: 'flex items-baseline justify-between gap-3' }, [
        el('span', { class: META, text: 'Your note so far' }),
        // The way to the summary, per NoteCard's onExpand: tapping the note
        // to read the whole thing is a more natural route than a button in
        // the action bar, and it leaves that bar the two slots the ActionBar
        // spec gives it.
        el('button', {
          type: 'button',
          class: 'cursor-pointer font-sans text-fact text-ink-muted underline',
          dataset: { action: 'review' },
          text: allAnswered(steps, state) ? 'Review ✓' : 'Review',
          onclick: onExpand,
        }),
      ]),
      el('p', { class: 'font-serif text-note' }, [
        note,
        // The unwritten half, in a ghosted colour: the sentence is visibly
        // incomplete, which is the point — it is being composed, not stored.
        el('span', { class: 'text-ink-ghost', text: note ? ' …' : '…' }),
      ]),
      el('div', { class: 'flex items-center gap-3' }, [
        renderProgressRail(steps, state, onJump),
        el('span', {
          class: 'shrink-0 font-mono text-meta text-ink-faint',
          text: `${pad(answered)}/${pad(p.total)}`,
        }),
      ]),
    ],
  );
}

/**
 * Render one option, with the guidance that says how to know it is this one.
 *
 * An observed scale gets a graded swatch per rung, drawn from the wine's depth
 * ramp — so "pale / medium / deep" is shown as well as named. The swatch is
 * never the only signal; the label is always there beside it (PRD §8).
 *
 * Whether a rung is marked at all is `hasRungMark`'s decision, not this
 * function's: the Conclude scales are ordered but carry no mark, because
 * there is no sensation for one to illustrate.
 *
 * @param {object} option
 * @param {object} question
 * @param {number} index - Position among its siblings, for the depth ramp.
 * @param {boolean} selected
 * @param {(code: string) => void} onPick
 * @param {boolean} marked - Does this question's scale carry rung marks?
 * @returns {HTMLElement}
 */
function renderOption(option, question, index, selected, onPick, marked) {
  const rung = Math.min(index + 1, 3);

  return el(
    'button',
    {
      type: 'button',
      class: `${OPTION} ${selected ? OPTION_ON : OPTION_OFF}`,
      'aria-pressed': selected ? 'true' : 'false',
      dataset: { code: option.code },
      onclick: () => onPick(option.code),
    },
    [
      // A solid disc, never a rim or a partial fill (WineSwatch). The
      // prototype outlines its palest rung; the spec forbids it, and the spec
      // wins — an outline on one rung and not the others makes the ramp read
      // as two different kinds of thing. The label carries the meaning
      // regardless (PRD §8), so a quiet disc costs nothing.
      option.swatch
        ? el('span', {
            class: 'size-10 shrink-0 rounded-full',
            style: `background:${option.swatch}`,
            'aria-hidden': 'true',
          })
        : null,
      !option.swatch && marked
        ? el('span', {
            class: `size-10 shrink-0 rounded-full bg-depth-${rung}`,
            'aria-hidden': 'true',
          })
        : null,
      el('span', { class: 'flex flex-col gap-1' }, [
        el('span', { class: 'font-serif text-answer', text: option.label }),
        option.guidance
          ? el('span', {
              class: 'font-sans text-fact text-ink-muted',
              text: option.guidance,
            })
          : null,
      ]),
    ],
  );
}

/**
 * Render the "why it matters" sheet.
 *
 * A sheet rather than a disclosure toggle: it is a paragraph the taster reads
 * once and dismisses, and inlining it would push the options off screen every
 * time somebody was curious.
 *
 * @param {string} text
 * @param {() => void} onClose
 * @returns {DocumentFragment} The scrim and the sheet.
 */
export function renderRubricSheet(text, onClose) {
  // Fixed to the viewport, not to the screen section. The design frames the
  // app in a fixed-height device, where "bottom of the container" and "bottom
  // of what you can see" are the same edge; on a real page that is only true
  // of the viewport, and anchoring to the section put the sheet below the
  // fold on a long question.
  const scrim = el('div', {
    class: 'fixed inset-0 z-20 bg-ink/20',
    dataset: { role: 'rubric-scrim' },
    'aria-hidden': 'true',
    onclick: onClose,
  });

  const sheet = el(
    'div',
    {
      class:
        'fixed inset-x-0 bottom-0 z-30 mx-auto flex max-w-measure flex-col gap-3 ' +
        'rounded-t-card border-t border-rule-strong bg-paper-raised px-5 pt-4 pb-8',
      role: 'dialog',
      'aria-modal': 'true',
      'aria-label': 'Why this matters',
      dataset: { role: 'rubric-sheet' },
    },
    [
      el('span', {
        class: 'h-1 w-10 self-center rounded-full bg-rule-strong',
        'aria-hidden': 'true',
      }),
      el('div', { class: 'flex items-center justify-between' }, [
        el('span', { class: META, text: 'Why this matters' }),
        el('button', {
          type: 'button',
          class: 'cursor-pointer font-sans text-caption text-ink-muted',
          dataset: { action: 'close-rubric' },
          text: 'Close',
          onclick: onClose,
        }),
      ]),
      el('p', { class: 'font-serif text-note', text }),
    ],
  );

  // One fragment so the caller appends both, and the scrim stays behind.
  const wrapper = document.createDocumentFragment();
  wrapper.append(scrim, sheet);
  return wrapper;
}

/**
 * Render the current question.
 *
 * @param {object} options
 * @param {Array<object>} options.steps
 * @param {object} options.state
 * @param {string} options.now - ISO timestamp.
 * @param {boolean} options.rubricOpen
 * @param {object} options.handlers
 * @returns {HTMLElement}
 */
export function renderQuestion({ steps, state, now, rubricOpen, handlers }) {
  const step = currentStep(steps, state);
  const { question } = step;
  const answered = state.answers[question.code] || { values: [], skipped: false };
  const p = progress(steps, state);
  const questions = questionStates(steps, state);
  const pad = (n) => String(n).padStart(2, '0');

  const screen = el('section', { class: 'relative flex flex-1 flex-col' });

  // Top bar: back, where you are, pause. Icon buttons at 40px, which is the
  // smallest thing on the screen and still comfortably tappable.
  screen.append(
    el('div', { class: 'flex items-center justify-between' }, [
      el(
        'button',
        {
          type: 'button',
          class: 'flex size-10 cursor-pointer items-center justify-center text-ink-muted',
          dataset: { action: 'back' },
          'aria-label': questions[state.cursor - 1]
            ? `Back to ${questions[state.cursor - 1].short}`
            : 'Back to setup',
          onclick: handlers.onBack,
        },
        [icon(CHEVRON_LEFT, { size: 22, width: 2 })],
      ),
      el('span', { class: META_LG }, [
        el('span', { text: step.phaseLabel }),
        ' ',
        el('span', {
          class: 'text-ink-faint',
          text: `${pad(p.step)}/${pad(p.total)}`,
        }),
        // The phase clock, as a word rather than a meter. PRD §5 wants a
        // pacing aid; the design forbids a second progress bar, and a filling
        // bar under the note card read as exactly that. This says the same
        // thing once, quietly, and only when there is something to say.
        isOverBudget(steps, state, now)
          ? el('span', { class: 'text-ink-faint', text: ' · over' })
          : null,
      ]),
      el('button', {
        type: 'button',
        class: 'flex size-10 cursor-pointer items-center justify-center font-sans text-caption text-ink-muted',
        dataset: { action: state.paused ? 'resume' : 'pause' },
        text: state.paused ? 'Go' : 'II',
        'aria-label': state.paused ? 'Resume' : 'Pause',
        onclick: state.paused ? handlers.onResume : handlers.onPause,
      }),
    ]),
  );

  screen.append(
    el('div', { class: 'mt-3' }, [
      renderNoteCard(steps, state, handlers.onJump, handlers.onReview),
    ]),
  );

  if (state.paused) {
    screen.append(
      el('p', {
        class:
          'mt-6 rounded-card border border-rule bg-paper-raised p-6 text-center font-sans text-body text-ink-muted',
        role: 'status',
        text: 'Paused. Nothing is lost — pick it up when you are ready.',
      }),
    );
    return screen;
  }

  // The question, its eyebrow, and the instruction that teaches it.
  screen.append(
    el('div', { class: 'mt-6 flex flex-col gap-2' }, [
      el('span', {
        class: META,
        text: `${step.phaseLabel} · ${question.short || question.code}`,
      }),
      el('h1', {
        class: 'text-pretty font-serif text-question font-normal',
        text: question.prompt,
      }),
      question.how
        ? el('div', { class: 'mt-1.5 flex items-start gap-3' }, [
            icon(LIGHTBULB, { size: 17, stroke: 'var(--color-accent)' }),
            el('p', {
              class: 'text-pretty font-sans text-body text-ink-muted',
              dataset: { role: 'how-to-tell' },
              text: question.how,
            }),
          ])
        : null,
    ]),
  );

  const marked = hasRungMark(step);
  const options = el('div', { class: 'mt-5 flex flex-col gap-2.5' });
  question.options.forEach((option, index) => {
    options.append(
      renderOption(
        option,
        question,
        index,
        answered.values.includes(option.code),
        handlers.onAnswer,
        marked,
      ),
    );
    // A category's descriptors appear once it is chosen, so the first screen
    // is a dozen rows rather than ninety.
    if (option.children?.length && answered.values.includes(option.code)) {
      const nested = el('div', {
        class: 'flex w-full flex-col gap-2 border-s-2 border-rule ps-3',
      });
      option.children.forEach((child, childIndex) => {
        nested.append(
          renderOption(
            child,
            question,
            childIndex,
            answered.values.includes(child.code),
            handlers.onAnswer,
            marked,
          ),
        );
      });
      options.append(nested);
    }
  });
  screen.append(options);

  if (question.why) {
    screen.append(
      el(
        'button',
        {
          type: 'button',
          class: 'mt-2.5 flex cursor-pointer items-center gap-2.5 px-0.5 py-1',
          dataset: { action: 'rubric' },
          'aria-expanded': rubricOpen ? 'true' : 'false',
          onclick: handlers.onRubric,
        },
        [
          el('span', {
            class:
              'flex size-5 items-center justify-center rounded-full border ' +
              'border-rule-strong font-mono text-meta-lg text-ink-muted',
            text: '?',
            'aria-hidden': 'true',
          }),
          el('span', {
            class: 'border-b border-rule-strong font-sans text-caption',
            text: 'Why it matters',
          }),
        ],
      ),
    );
  }

  if (answered.skipped) {
    screen.append(
      el('p', {
        class: 'mt-3 font-sans text-fact text-ink-muted',
        text: 'Marked as unsure. You can come back to it.',
      }),
    );
  }

  // The action bar, pinned to the bottom of the screen and tinted with the
  // wine's own bar colour. Back is the icon; forward names its destination,
  // because "Depth →" tells you what you are about to see where "Next" only
  // tells you which way you are going.
  const forward = questions[state.cursor + 1];
  screen.append(
    el(
      'div',
      {
        class:
          '-mx-4 mt-auto flex items-center gap-2.5 border-t border-rule bg-bar ' +
          'px-4 pt-3.5 pb-6 sm:-mx-6 sm:px-6',
      },
      [
        el('button', {
          type: 'button',
          class: SECONDARY,
          dataset: { action: 'back' },
          text: '←',
          'aria-label': questions[state.cursor - 1]
            ? `Back to ${questions[state.cursor - 1].short}`
            : 'Back to setup',
          onclick: handlers.onBack,
        }),
        el('button', {
          type: 'button',
          class: PRIMARY,
          dataset: { action: 'next' },
          text: forward ? `${forward.short} →` : 'Review and save',
          onclick: handlers.onNext,
        }),
      ],
    ),
  );

  if (rubricOpen && question.why) {
    screen.append(renderRubricSheet(question.why, handlers.onRubric));
  }

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
  section.append(el('h2', { class: META, text: 'What that tells you' }));

  reading.groups.forEach((group) => {
    section.append(
      el('div', { dataset: { origin: group.origin } }, [
        el('p', { class: META, text: group.label }),
        el('p', { class: 'font-sans text-body', text: group.descriptors.join(', ') }),
      ]),
    );
  });

  reading.conclusions.forEach((conclusion) => {
    section.append(
      el(
        'div',
        { class: 'border-t border-rule pt-3', dataset: { inference: conclusion.code } },
        [
          el('p', { class: 'font-serif text-answer', text: conclusion.label }),
          el('p', {
            class: 'font-sans text-fact text-ink-muted',
            // Shows its working. "Because you found butter and cream" is the
            // teaching half; the label on its own is one more thing to learn
            // by rote.
            text: `Because you found ${conclusion.evidence.join(', ')}.`,
          }),
          el('p', {
            class: 'mt-1 font-sans text-fact',
            text: conclusion.explanation,
          }),
        ],
      ),
    );
  });

  return section;
}

/**
 * Render the closing summary: the note, what it means, then the save.
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
  const screen = el('section', { class: 'flex flex-1 flex-col gap-5' });
  const note = noteSoFar(steps, state);

  screen.append(
    el('div', { class: 'flex flex-col gap-2' }, [
      el('span', { class: META, text: 'Tasting complete' }),
      el('h1', { class: 'font-serif text-question font-normal', text: 'Your note' }),
    ]),
    // The same card that led every question screen, finished.
    el(
      'section',
      {
        class:
          'rounded-card border border-rule border-t-3 border-t-accent ' +
          'bg-paper-raised px-4 py-4',
        dataset: { role: 'note-card' },
      },
      [
        el('p', { class: 'font-serif text-note' }, [
          note || 'Nothing recorded',
          el('span', {
            class: 'text-ink-ghost',
            text: note ? ' — saved as written.' : '',
          }),
        ]),
      ],
    ),
  );

  const readingBlock = renderReading(reading);
  if (readingBlock) screen.append(readingBlock);

  let phase = null;
  const list = el('dl', { class: 'flex flex-col gap-2.5' });
  steps.forEach((step, index) => {
    const answered = state.answers[step.question.code];
    if (!answered) return;
    if (step.phase !== phase) {
      phase = step.phase;
      list.append(el('dt', { class: `${META} mt-3`, text: step.phaseLabel }));
    }
    list.append(
      el('dd', { class: 'flex items-baseline gap-3 border-b border-rule pb-2.5' }, [
        el('span', {
          class: `${META} w-20 shrink-0`,
          text: step.question.short || step.question.prompt,
        }),
        el('span', {
          class: answered.skipped
            ? 'flex-1 font-sans text-body text-ink-disabled'
            : 'flex-1 font-sans text-body',
          text: answered.skipped
            ? 'Not recorded'
            : answered.values.map((v) => labelFor(step.question.code, v)).join(', '),
        }),
        // Every line is a way back to the question that produced it. Reaching
        // an answer you want to change should not mean walking backwards
        // through the ones you were happy with.
        el('button', {
          type: 'button',
          class: 'cursor-pointer font-sans text-fact text-ink-muted underline',
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
      class:
        'rounded-control border border-rule bg-paper-raised px-4 py-3 font-sans text-body',
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
        [el('label', { class: META, for: 'actual-grape', text: 'What was it really?' }), grape],
      ),
    );
  }

  screen.append(
    el(
      'div',
      {
        class:
          '-mx-4 mt-auto flex items-center gap-2.5 border-t border-rule bg-bar ' +
          'px-4 pt-3.5 pb-6 sm:-mx-6 sm:px-6',
      },
      [
        el('button', {
          type: 'button',
          class: SECONDARY,
          dataset: { action: 'back' },
          text: '←',
          'aria-label': 'Back to the questions',
          onclick: handlers.onBack,
        }),
        el('button', {
          type: 'button',
          class: PRIMARY,
          dataset: { action: 'save' },
          text: 'Save to journal',
          onclick: handlers.onSave,
        }),
      ],
    ),
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
