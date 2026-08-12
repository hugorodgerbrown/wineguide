# Design system

The rules the session UI follows, pulled from the Claude Design project
**Wine Tasting Guide Design Directions**
(`86d6c49a-efce-4228-9d39-1cdb15424e6d`) — its `guidelines/` and
`components/` specs.

They are recorded here because the source is a remote project this repo cannot
read at build time, and a rule nobody can find is a rule that gets broken. The
tokens themselves live in [src/css/main.css](../src/css/main.css); this is the
part that is not expressible as a token.

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
