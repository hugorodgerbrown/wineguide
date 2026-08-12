/*
 * tests/js/test_session_inference.js — The client half of the deduction.
 *
 * Deliberately parallel to tests/lexicon/test_inference.py. The same rule runs
 * in both places, because the journal is server-rendered and the closing
 * summary has to work offline. A case added there should be added here.
 */

import { describe, expect, it } from 'vitest';

import {
  indexDescriptors,
  interpret,
  selectedCodes,
} from '../../static/js/session/session_inference.js';

/** A descriptor, in payload shape. */
const d = (code, label, origin, implies = '') => ({
  code,
  label,
  guidance: '',
  origin,
  implies,
  swatch: '',
});

const PAYLOAD = {
  version: '2026.1',
  wine_type: 'still_white',
  phases: [
    {
      code: 'smell',
      label: 'Smell',
      seconds: 90,
      questions: [
        {
          code: 'aromas',
          prompt: 'What can you smell?',
          short: 'Aromas',
          how: '',
          why: '',
          control: 'multi',
          options: [
            {
              ...d('baking', 'Bread and pastry', ''),
              children: [d('brioche', 'Brioche', 'secondary', 'lees')],
            },
            {
              ...d('dairy', 'Dairy', ''),
              children: [
                d('butter', 'Butter', 'secondary', 'malolactic'),
                d('cream', 'Cream', 'secondary', 'malolactic'),
              ],
            },
            {
              ...d('citrus', 'Citrus', ''),
              children: [d('lemon', 'Lemon', 'primary')],
            },
            {
              ...d('earth', 'Earth', ''),
              children: [d('mushroom', 'Mushroom', 'tertiary', 'bottle_age')],
            },
          ],
        },
      ],
    },
    {
      code: 'taste',
      label: 'Taste',
      seconds: 150,
      questions: [
        {
          code: 'acidity',
          prompt: 'How much acidity?',
          short: 'Acidity',
          how: '',
          why: '',
          control: 'scale',
          // Untagged: a scale answer is not a descriptor.
          options: [{ ...d('high', 'High', ''), children: [] }],
        },
        {
          code: 'flavours',
          prompt: 'What can you taste?',
          short: 'Flavours',
          how: '',
          why: '',
          control: 'multi',
          options: [
            {
              ...d('dairy', 'Dairy', ''),
              children: [d('butter', 'Butter', 'secondary', 'malolactic')],
            },
          ],
        },
      ],
    },
  ],
  inferences: [
    { code: 'lees', label: 'Time on the lees', explanation: 'What lees means.' },
    {
      code: 'malolactic',
      label: 'Malolactic conversion',
      explanation: 'What malolactic means.',
    },
    { code: 'bottle_age', label: 'Bottle age', explanation: 'What age means.' },
  ],
};

const stateWith = (...codes) => ({
  answers: { aromas: { values: codes, skipped: false } },
});

describe('indexDescriptors', () => {
  it('finds descriptors at both levels of the tree', () => {
    const index = indexDescriptors(PAYLOAD);
    expect(index.get('brioche')).toEqual({
      label: 'Brioche',
      origin: 'secondary',
      implies: 'lees',
    });
  });

  it('skips options carrying neither tag', () => {
    // Scale rungs and bare categories are not descriptors.
    const index = indexDescriptors(PAYLOAD);
    expect(index.has('high')).toBe(false);
    expect(index.has('citrus')).toBe(false);
  });

  it('survives an empty payload', () => {
    expect(indexDescriptors({}).size).toBe(0);
  });
});

describe('selectedCodes', () => {
  it('flattens every answer', () => {
    const codes = selectedCodes({
      answers: {
        aromas: { values: ['lemon', 'butter'] },
        acidity: { values: ['high'] },
      },
    });
    expect([...codes].sort()).toEqual(['butter', 'high', 'lemon']);
  });

  it('is empty for a session with no answers', () => {
    expect(selectedCodes({ answers: {} }).size).toBe(0);
  });
});

describe('origin groups', () => {
  it('sorts descriptors into the framework', () => {
    // The taster records what they smell; the app does the filing.
    const { groups } = interpret(PAYLOAD, stateWith('lemon', 'brioche', 'mushroom'));
    expect(groups.map((g) => [g.origin, g.descriptors])).toEqual([
      ['primary', ['Lemon']],
      ['secondary', ['Brioche']],
      ['tertiary', ['Mushroom']],
    ]);
  });

  it('comes in teaching order regardless of what was picked first', () => {
    const { groups } = interpret(PAYLOAD, stateWith('mushroom', 'lemon'));
    expect(groups.map((g) => g.origin)).toEqual(['primary', 'tertiary']);
  });

  it('omits an origin with nothing in it', () => {
    const { groups } = interpret(PAYLOAD, stateWith('lemon'));
    expect(groups.map((g) => g.origin)).toEqual(['primary']);
  });

  it('ignores untagged answers', () => {
    const state = { answers: { acidity: { values: ['high'] } } };
    expect(interpret(PAYLOAD, state).groups).toEqual([]);
  });

  it('counts a descriptor found on the nose and the palate once', () => {
    const state = {
      answers: {
        aromas: { values: ['butter'] },
        flavours: { values: ['butter'] },
      },
    };
    expect(interpret(PAYLOAD, state).groups[0].descriptors).toEqual(['Butter']);
  });
});

describe('conclusions', () => {
  it('names the process behind the descriptor', () => {
    // The point of the whole exercise: the taster is told, not asked.
    const { conclusions } = interpret(PAYLOAD, stateWith('butter'));
    expect(conclusions.map((c) => c.code)).toEqual(['malolactic']);
    expect(conclusions[0].label).toBe('Malolactic conversion');
  });

  it('shows its working', () => {
    const { conclusions } = interpret(PAYLOAD, stateWith('butter', 'cream'));
    expect(conclusions[0].evidence).toEqual(['Butter', 'Cream']);
  });

  it('fires on a single descriptor', () => {
    // No threshold. One descriptor is enough for a true sentence, and a
    // confidence score would imply a precision this does not have.
    const { conclusions } = interpret(PAYLOAD, stateWith('brioche'));
    expect(conclusions.map((c) => c.code)).toEqual(['lees']);
  });

  it('draws several at once, in the lexicon order', () => {
    const { conclusions } = interpret(
      PAYLOAD,
      stateWith('mushroom', 'butter', 'brioche'),
    );
    expect(conclusions.map((c) => c.code)).toEqual([
      'lees',
      'malolactic',
      'bottle_age',
    ]);
  });

  it('draws nothing from an empty session', () => {
    const reading = interpret(PAYLOAD, { answers: {} });
    expect(reading).toEqual({ groups: [], conclusions: [] });
  });

  it('ignores an implication with no inference defined', () => {
    // A descriptor tagged with a code nobody explained is a data error, and
    // must not render as an empty conclusion.
    const payload = {
      ...PAYLOAD,
      phases: [
        {
          code: 'smell',
          label: 'Smell',
          seconds: 90,
          questions: [
            {
              code: 'aromas',
              control: 'multi',
              options: [{ ...d('banana', 'Banana', 'primary', 'carbonic'), children: [] }],
            },
          ],
        },
      ],
    };
    const reading = interpret(payload, stateWith('banana'));
    expect(reading.groups.map((g) => g.origin)).toEqual(['primary']);
    expect(reading.conclusions).toEqual([]);
  });

  it('survives a payload with no inferences at all', () => {
    const payload = { ...PAYLOAD, inferences: undefined };
    expect(interpret(payload, stateWith('butter')).conclusions).toEqual([]);
  });
});
