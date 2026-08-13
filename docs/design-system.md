# Design system

The rules the session UI follows, pulled from the Claude Design project
**Wine Tasting Guide Design Directions**
(`86d6c49a-efce-4228-9d39-1cdb15424e6d`) — its `guidelines/` and
`components/` specs.

They are recorded here because the source is a remote project this repo cannot
read at build time, and a rule nobody can find is a rule that gets broken. The
tokens themselves live in [src/css/main.css](../src/css/main.css); this is the
part that is not expressible as a token.

## What was built, published back

`bin/export_design_system.py` renders the implemented system — the tokens, the
five wine themes, and a preview card per session component — into
`design-export/`, which is then pushed with the DesignSync MCP to:

> **Wineguide — as built** ·
> https://claude.ai/design/p/8019a23f-e49f-43dc-8714-fe5ebb8583d4

A separate project from the source directions on purpose: that one is the
brief, this one is what got built, and a diff between them is the useful
thing. The script never writes to the source.

The bundle is a build artefact and is gitignored; the script is what is
versioned, and it reads every token straight out of `main.css` rather than
keeping a second copy that would be wrong within a month.

## The two that shape the screen

**Progress is the note filling in.** There is exactly one progress indicator
in a session — the note card, with its markers and count. Do not add a second
bar anywhere. The phase time budget (PRD §5) is a word in the header when it
is spent, not a meter, for this reason.

**The taster is told, not asked.** The guided flow records observations, and
the app draws the conclusions. See `apps/lexicon/inference.py`.

## Colour

- **Accent appears only on** the note-card top rule, the current dot, the hint
  icon, the advance button, and a selected option's border. Nowhere else — an
  accent on everything is an accent on nothing.
- **Progress dots take the wine's depth ramp**, not the accent. Answered
  solid, current a 2px ring, upcoming a hairline outline. Once the depth
  question is answered the whole row stains itself that rung, so a pale wine
  gets a pale row (`depthRung` in `session_core.js`).
- **Warm neutrals throughout.** Never a cool grey.
- **No shadows anywhere.** Warm hairlines on warm paper do the separating.

## Type

Three roles, and nothing crosses between them:

| Role | Face | Used for |
| --- | --- | --- |
| Serif | `font-serif` | Question headline (34px), answer labels (23px), the note prose (19px) |
| Sans | `font-sans` | Body, guidance, controls |
| Mono | `font-mono` | Meta — small, tracked, uppercase labels and counters |

The question headline is the only type above 24px in a session.

## Components

- **QuestionTitle** — one question per screen, phrased as a plain question,
  sentence case. No jargon in the headline; the technical term lives in the
  answers.
- **HintPanel** — procedural: *how* to make the observation. Two sentences,
  readable in under three seconds, one-handed. Distinct from the rubric,
  which is *why it matters*.
- **RubricSheet** — the teaching layer, over the bottom of the screen so it is
  in thumb reach.
- **OptionRow** — tap-to-select, never free text. 76px minimum, 10px gaps,
  full gutter width. Selected is a raised fill plus an accent border. No hover
  state — this is a touch surface.
- **ScaleMark** — nine marks, **one per sensory axis rather than one per
  question**, so a question added later inherits an existing drawing and
  nothing new has to be invented. The axis is data (`Axis` in
  `apps/core/enums.py`, on `Question`, in the payload), which is what makes
  that true. Every mark is themed accent — quiet unselected, full accent
  selected — and **never the wine's depth ramp**: colour belongs to the colour
  questions. The unreached part of a scale is always drawn, always a hairline
  dot in ink-ghost, because it is scaffolding rather than an answer. A mark
  never carries a number and never appears without its label.

  | Mark | Axis | Questions |
  | --- | --- | --- |
  | Carry | Distance it travels to you | Smell intensity |
  | Burst | How much arrives at once | Flavour intensity |
  | Fill | Quantity on the tongue | Sweetness |
  | Spread | How far across the mouth | Acidity |
  | Rise | Warmth climbing the throat | Alcohol |
  | Weight | Thickness | Body |
  | Grain | Friction and grip | Tannin, Bubbles |
  | Length | Time after swallowing | Finish |
  | Swatch | Hue and depth | Depth, Colour |

  **Everything in Conclude is unmarked, and so is anything categorical.** A
  mark illustrates a sensation; "faulty → outstanding" and "guessing →
  confident" are ordered, but they are judgements the taster arrives at rather
  than sensations they receive, so there is no geometry to draw. A mark means
  *you observed this* and a plain row means *you decided this* — the same seam
  `noteSoFar` draws when it leaves Conclude out of the sentence.

  Classifying a new question: which sense answers it; where in the body it is
  felt; is it an amount, a reach or a texture. If none of those fit, it is not
  a scale and takes no mark.

  The geometry is in the components layer of `main.css` keyed on
  `[data-axis]`, because none of it is expressible as a utility. Sizes
  interpolate from `--reach` rather than being three fixed rungs, which is
  what lets sweetness draw five and everything else three from one rule
  (`markAxis` and `markReach` in `session_core.js`).
- **WineSwatch** — a whole filled circle. **Never a rim, edge or partial
  fill**; depth reads as one solid disc, always from `--color-depth-1..3` so
  the same component reads lemon in a white session and ruby in a red one.
- **ActionBar** — foot of every session screen. Back on the left as an arrow
  only, advance filling the remaining width. **There is no skip control**:
  advancing without a selection records the question as unanswered.
- **Button** — labels name the destination ("Hue →"), never "Next" alone.
  52px minimum. No shadow, no scale on press — opacity only.
- **SessionHeader** — pause is always reachable; a real tasting gets
  interrupted.

## Where this build departs

Both were decisions taken deliberately, and both are also noted at the point
of departure in the code.

1. **System fonts, not the specified Google Fonts.** The three roles are kept
   exactly; the faces are system stacks. The session page is precached to run
   offline (PRD §8), and a CDN font would be the one thing on it that is not
   there in a cellar. Self-hosting the three families would close this.
2. **Dark counterparts for every wine theme.** The design is light-only. The
   app has a working theme toggle, so each theme declares a lifted accent for
   dark. The depth ramp deliberately does not — it stands for the colour of
   the wine in the glass, and a Barolo is not lighter because the phone is.

One place the source disagrees with itself: the prototype's `QuestionScreen`
outlines the palest depth swatch, which `WineSwatch` forbids. The spec wins —
an outline on one rung and not the others makes the ramp read as two different
kinds of thing, and the label carries the meaning regardless (PRD §8).
