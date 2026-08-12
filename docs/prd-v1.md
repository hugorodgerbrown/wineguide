# Product Requirements Document
## Guided Wine Tasting Companion (working title)

**Status:** Draft v0.1 — for review
**Owner:** [You]
**Last updated:** August 12, 2026

---

## 1. Problem Statement

WSET students (Levels 1–3) learn a structured method for tasting — the Systematic Approach to Tasting (SAT) — but between classes they practice alone, without a prompt telling them what to look for or when. The result: inconsistent notes, skipped steps, and a method that never becomes muscle memory.

This app puts a structured, timed prompt sequence in the taster's hand *while the glass is in front of them* — turning a mental checklist into a guided, real-time routine — and captures the result in a personal journal so progress and pattern-recognition compound over time.

## 2. Goals

| Goal | Why it matters |
|---|---|
| Make the 4-phase tasting sequence (Look → Smell → Taste → Conclude) a repeatable physical habit | This is the core learning outcome — repetition builds the "muscle memory" the user described |
| Reduce blank-page paralysis | Structured prompts + tap-to-select vocabulary beat free-text notes for speed and consistency |
| Build a private, searchable record of every tasting | Enables users to notice their own patterns (e.g. "I keep guessing high-acid whites as Sauvignon Blanc") |
| Get users to a plausible grape/origin/method guess by the end of each session | This is the "so what" of the method — SAT isn't just description, it's deduction |

### Non-goals for v1
- Turning tasting into a game or competitive quiz (deferred — see §10)
- Building a wine database, label scanner, or price lookup (deferred)
- Social feed, sharing, or leaderboards (deferred)
- Native iOS/Android apps (v1 is web/PWA only, per platform decision)

## 3. Target User

**Primary persona: the WSET Level 1–3 student.**
Taking or has recently taken a WSET course. Knows the SAT vocabulary exists but hasn't internalized the sequence or the calibration (what actually separates "medium" from "pronounced" intensity). Tastes at home, at a wine bar, or in a study group — usually with limited time and a wine that's oxidizing while they think. Comfortable with a phone or laptop; not necessarily comfortable typing detailed notes one-handed while holding a glass.

**Jobs to be done:**
1. "Walk me through the method so I don't skip a step or freeze up."
2. "Give me the right vocabulary so I'm not guessing at terminology."
3. "Keep a record so I can look back and see if I'm actually improving."

## 4. Success Metrics

- **Session completion rate**: % of started sessions that reach the Conclude phase (target: >70%)
- **Habit formation**: sessions per active user per week (target: 2+, roughly matching a study cadence)
- **Journal engagement**: % of completed sessions the user revisits later (view or edit)
- **Self-reported confidence**: simple in-app pulse ("How confident do you feel identifying acidity today?") tracked over time
- **Retention**: W1 → W4 return rate

## 5. Core User Journey

The whole product is built around one repeatable, timed loop. See the attached flow diagram (`wine_tasting_flow.mermaid`) for the visual version — this section is the spec behind it.

| Phase | Time budget | What the app asks | WSET concept reinforced |
|---|---|---|---|
| **Look** | 30–60 sec | Clarity, intensity, colour (options adapt to wine type: still white/red/rosé, sparkling, fortified) | Appearance as first-pass evidence of grape/age/climate |
| **Smell** | 1–2 min | Condition (clean/faulty), intensity, then aroma characteristics sorted into **primary** (fruit/floral/herbal — from the grape), **secondary** (yeast/oak/malolactic — from winemaking), **tertiary** (bottle age/oxidation — from maturation) | The primary/secondary/tertiary framework the user specifically called out |
| **Taste** | 2–3 min | Structural components — sweetness, acidity, tannin, alcohol, body — each on a low/medium/high (or dry→sweet) scale, then flavour intensity & characteristics, then finish | Structure as the "chemistry" of the wine, separate from flavour |
| **Conclude** | 1–2 min | Quality assessment, readiness/ageing potential, and a **guess**: grape variety, likely origin, and winemaking clues (oak? malolactic? skin contact?) with a confidence slider | The deductive payoff — turning observations into a hypothesis |

Each phase auto-advances on a soft timer but is user-controlled: pause, extend, or tap "Next" early. This isn't a race — the timer is a pacing aid, not a countdown clock, since rushing a beginner defeats the purpose.

## 6. Feature Requirements — v1

### 6.1 Guided Tasting Session (core loop)

**Setup**
- Select wine type (still white / still red / rosé / sparkling / fortified) — determines which colour and structure options are shown, since "garnet" doesn't apply to a Chardonnay
- Optional: name the wine / producer up front, or leave blank and fill in after tasting blind (supports actual blind-tasting practice)

**Phase screens (Look / Smell / Taste / Conclude)**
- One question per screen, large tap targets, WSET-standard options shown as chips/segmented controls — **not free text**, so the user is选ecting correct terminology rather than inventing their own
- Optional short "why this matters" tooltip per question (e.g., tapping on Tannin explains what it feels like and why it matters) — a light teaching layer, not a full course
- Progress indicator showing which of the 4 phases they're in
- Pause/resume — critical for a real tasting where someone interrupts you
- Skip a question if genuinely unsure, marked as "skipped" rather than forcing a guess

**Session end**
- Full SAT summary shown back to the user (all selections, one screen)
- Prompt to reveal/enter the actual wine (if tasted blind) so the guess can be scored against reality
- One tap to save to journal

### 6.2 Personal Tasting Journal

- Every completed (and in-progress/abandoned) session auto-saves — nothing is lost if they close the tab
- **List view**: date, wine name (if known), quick tags (grape/type/quality rating), thumbnail of colour
- **Detail view**: full SAT breakdown as recorded, plus the guess vs. actual reveal if provided
- **Search & filter**: by grape, region, wine type, date range, quality rating
- **Edit**: correct or add notes after the fact (e.g., filling in the producer once they check the label)
- **Delete**: remove an entry

*Deferred to v1.1:* side-by-side comparison of two entries — valuable but not required to validate the core loop.

### 6.3 WSET Lexicon & Guidance Data

- Vocabulary options per phase should be modeled as structured, versioned data (not hardcoded per-screen strings) so it can be corrected or extended without a code change, and so it can eventually scale to Level 3 detail without a rebuild
- Aroma/flavour characteristics should be organized the way the method teaches them — broad category first (e.g., citrus fruit), specific descriptor second (grapefruit, lemon, lime) — mirroring how a taster actually narrows in

### 6.4 Accounts

- Lightweight auth (email/passwordless or OAuth) — the journal is only useful if it persists across devices and sessions
- No profile/social features beyond what's needed for login in v1

## 7. UX Principles (specific to this product)

This app is used **at the table, glass in one hand**, often in bad lighting, sometimes after a couple of pours. Design constraints follow from that:

- **Minimal typing.** Tap-to-select over free text everywhere in the guided flow; typing is reserved for the wine name and optional notes.
- **Legible under pressure.** High contrast, large type, short prompts readable in under 3 seconds — this is not a reading app.
- **One-handed operation.** Primary actions reachable by thumb; no complex gestures.
- **Forgiving, not gamified (in v1).** No score, no streaks, no red "you're wrong" — v1 is about method, not competition. (Save the scoring/game layer for the guessing-game phase in the roadmap.)
- **Interruption-safe.** Someone will refill your glass or ask a question mid-session — pause state must be bulletproof, and nothing should be lost on accidental navigation away.

## 8. Non-Functional Requirements

- **Installable PWA** with offline support for an in-progress session — venue wifi/cellular is often unreliable, and a session shouldn't die because connectivity dropped between Look and Smell
- **Fast phase transitions** (<200ms) — any lag between tapping "Next" and the next prompt breaks the real-time pacing that's the whole point
- **Data privacy** — tasting notes are personal; no data sale, clear export/delete-my-data path
- **Accessibility** — sufficient contrast and scalable text; colour-blind-safe indicators for wine colour selection (don't rely on colour swatches alone)

## 9. Technical Considerations

Given a Python/Django background, a reasonable v1 shape:

- **Backend**: Django + Django REST Framework, exposing session and journal endpoints; Postgres for storage
- **Frontend**: PWA (React or Vue) with a service worker (Workbox) so an in-progress session survives connectivity loss and syncs on reconnect
- **Session state**: held client-side during the live tasting for instant phase transitions, persisted to the backend on pause/save rather than round-tripping the server on every tap
- **Lexicon data**: served as versioned, structured config (JSON/DB-backed) rather than hardcoded in templates, so terminology can be corrected or extended per SAT level without a deploy
- **Data model (sketch)**: `TastingSession` (wine type, timestamps, status) → `PhaseResponse` (phase, field, selected value(s)) → `Conclusion` (quality, readiness, guessed grape/origin/method, confidence, actual wine if revealed)

## 10. Explicitly Out of Scope for v1

| Deferred feature | Rough phase |
|---|---|
| Grape/region guessing game mode (scored, replayable) | v2 |
| Wine database / label or barcode scan | v2–v3 |
| Side-by-side comparison of journal entries | v1.1 |
| Social sharing / following / leaderboards | v3 |
| Native iOS/Android apps | Revisit after PWA validates the loop |
| Wine recommendations, cellar/price tracking | Not currently planned |

## 11. Open Questions & Risks

- **Trademark/IP risk (important, flag early):** "Systematic Approach to Tasting" and the associated lexicon documents are copyrighted and trademarked by WSET. The *underlying method* (look/smell/taste/conclude, structural components, primary/secondary/tertiary) is a widely-taught, industry-standard framework and fine to build around — but reproducing WSET's own copyrighted documents, using their trademarked name as your product name, or implying WSET endorsement would need their permission. Worth a short conversation with a lawyer or with WSET directly before launch, not after.
- **Pacing calibration**: will the suggested phase timings feel right for a true beginner vs. someone finishing Level 3? May need a "pace" setting (relaxed/standard) rather than one fixed timer.
- **Blind vs. sighted tasting**: does v1 support both, or default to one? Affects whether "enter the wine" happens before or after the session.
- **Multi-wine flights**: WSET classes often taste 3–6 wines in a sitting. Is v1 single-wine-per-session only, with flights as a v1.1 wrapper, or does the session model need to support flights from day one?

## 12. Roadmap (indicative)

1. **v1** — Guided tasting flow + personal journal (this PRD)
2. **v1.1** — Flight support, journal comparison view, pacing presets
3. **v2** — Grape/region guessing game mode (scored, replayable, the natural next step once the core method is second nature)
4. **v3** — Wine database, label/barcode lookup, optional social features

---

*Companion diagram: `wine_tasting_flow.mermaid` — visualizes the minute-by-minute flow described in §5.*
