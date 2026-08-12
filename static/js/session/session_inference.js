/*
 * static/js/session/session_inference.js — Turning descriptors into conclusions.
 *
 * The client half of apps/lexicon/inference.py. Two implementations exist
 * because the closing summary has to work with no network (PRD §8) and the
 * journal is server-rendered — so the same rule has to run in both places.
 * They read the same `origin` and `implies` tags out of the same lexicon
 * payload, and their test suites are deliberately parallel: if you change the
 * rule here, change it there.
 *
 * The rule: an inference fires if any descriptor tagged with it was chosen.
 * No thresholds, no weighting, no confidence score — "you found butter, which
 * usually means malolactic conversion" is a true and useful sentence on one
 * descriptor, and a percentage would imply a precision this does not have.
 *
 * The point of all of it: the taster is never asked whether a wine went
 * through malolactic conversion. They are asked what they can smell, and told
 * what it means.
 */

/** Origins in the order they are taught, and the order they are shown. */
export const ORIGINS = [
  { code: 'primary', label: 'From the grape' },
  { code: 'secondary', label: 'From the winemaking' },
  { code: 'tertiary', label: 'From age' },
];

/**
 * Index every descriptor in a payload by its option code.
 *
 * Walks both levels of the option tree, across every question, because the
 * aroma vocabulary appears twice — once on the nose, once on the palate — and
 * a descriptor found in both places is one finding, not two.
 *
 * @param {object} payload - The lexicon payload.
 * @returns {Map<string, {label: string, origin: string, implies: string}>}
 */
export function indexDescriptors(payload) {
  const index = new Map();
  const add = (option) => {
    if (!option.origin && !option.implies) return;
    index.set(option.code, {
      label: option.label,
      origin: option.origin || '',
      implies: option.implies || '',
    });
  };
  (payload.phases || []).forEach((phase) => {
    (phase.questions || []).forEach((question) => {
      (question.options || []).forEach((option) => {
        add(option);
        (option.children || []).forEach(add);
      });
    });
  });
  return index;
}

/**
 * Every option code a session selected, across every question.
 *
 * @param {object} state - Session state from session_core.
 * @returns {Set<string>}
 */
export function selectedCodes(state) {
  const codes = new Set();
  Object.values(state.answers || {}).forEach((answer) => {
    (answer.values || []).forEach((code) => codes.add(code));
  });
  return codes;
}

/**
 * Sort the chosen descriptors by origin and say what they imply.
 *
 * @param {object} payload - The lexicon payload, for the tags and the
 *   inference wording.
 * @param {object} state - Session state from session_core.
 * @returns {{groups: Array<object>, conclusions: Array<object>}}
 */
export function interpret(payload, state) {
  const index = indexDescriptors(payload);
  const chosen = selectedCodes(state);

  const byOrigin = new Map();
  const byInference = new Map();
  chosen.forEach((code) => {
    const descriptor = index.get(code);
    if (!descriptor) return;
    if (descriptor.origin) {
      if (!byOrigin.has(descriptor.origin)) byOrigin.set(descriptor.origin, new Set());
      byOrigin.get(descriptor.origin).add(descriptor.label);
    }
    if (descriptor.implies) {
      if (!byInference.has(descriptor.implies)) {
        byInference.set(descriptor.implies, new Set());
      }
      byInference.get(descriptor.implies).add(descriptor.label);
    }
  });

  const sorted = (set) => [...set].sort((a, b) => a.localeCompare(b));

  return {
    groups: ORIGINS.filter((o) => byOrigin.has(o.code)).map((o) => ({
      origin: o.code,
      label: o.label,
      descriptors: sorted(byOrigin.get(o.code)),
    })),
    conclusions: (payload.inferences || [])
      .filter((inference) => byInference.has(inference.code))
      .map((inference) => ({
        code: inference.code,
        label: inference.label,
        explanation: inference.explanation,
        // The descriptors that fired it, so the app shows its working rather
        // than pronouncing. "Because you found butter" is the teaching half.
        evidence: sorted(byInference.get(inference.code)),
      })),
  };
}
