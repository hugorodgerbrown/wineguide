# wineguide

A guided tasting companion for wine students. It walks you through the
four-phase sequence — Look, Smell, Taste, Conclude — with the glass in front of
you, and keeps every session in a personal journal.

Django + HTMX + Tailwind, with the live tasting running client-side. The spec
is [docs/prd-v1.md](docs/prd-v1.md); the flow is
[docs/tasting-flow.mermaid](docs/tasting-flow.mermaid).

## Requirements

- Python 3.14 (`.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Node 20 (Tailwind, JS unit tests, vendoring)

## Setup

```bash
cp .env.example .env
```

Put a real key in `SECRET_KEY`:

```bash
uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Then install everything, build the stylesheet, and start the server:

```bash
uv sync && npm install && npm run build:css && uv run python manage.py migrate && uv run python manage.py runserver
```

While working on templates, keep Tailwind watching in a second terminal:

```bash
npm run watch:css
```

Install the git hooks once:

```bash
uv run pre-commit install
```

`.env` is gitignored, so a fresh git worktree needs its own copy before the
dev server will boot.

## Running things

`tox` is the entrypoint for every check. CI runs the same envs, so a green
`tox` locally means a green CI.

```bash
uv run tox
```

That runs the default list: `fmt`, `lint`, `djangofmt`, `mypy`,
`django-checks`, `test`, `js`. Individual envs:

| Command | What it does |
| --- | --- |
| `uv run tox -e fmt` | `ruff format --check` |
| `uv run tox -e lint` | `ruff check` |
| `uv run tox -e djangofmt` | Template formatting (fails if it had to change anything) |
| `uv run tox -e mypy` | Type checks over `apps/`, `config/`, `tests/` |
| `uv run tox -e django-checks` | `manage.py check` plus a missing-migrations check |
| `uv run tox -e test` | pytest with coverage (90% floor) |
| `uv run tox -e js` | Vitest (jsdom) |
| `uv run tox -e e2e` | Playwright / Chromium — opt-in, not in the default list |
| `uv run tox -e audit` | pip-audit over runtime dependencies |
| `uv run tox -e audit-dev` | pip-audit over dev groups + `npm audit` (detection only) |
| `uv run tox -e sast` | semgrep |

To run one e2e file:

```bash
uv run tox -e e2e -- tests/e2e/test_home.py
```

## Layout

```
apps/core/          Enums shared by the lexicon and the record; the SW view
apps/accounts/      Passwordless sign-in — a signed link, no passwords
apps/lexicon/       The versioned vocabulary, and the payload the client runs on
apps/tastings/      The tasting record, the session shell, and two JSON endpoints
apps/journal/       Reading sessions back: list, detail, search, edit, delete
apps/public/        The landing page
config/             Settings (base / development / production), URLs, WSGI
templates/          Site-wide templates — base.html, includes, offline page
src/css/main.css    Tailwind entry point and every design token
static/css/         Build output (output.css, gitignored)
static/js/session/  The session state machine — core, db, sync, ui, controller
static/js/          theme.js, sw.js, sw_register.js
static/js/vendor/   Third-party JS, copied from node_modules and committed
tests/              pytest, mirroring the apps
tests/js/           Vitest — the client-side modules
tests/e2e/          Playwright — the paths that need a real browser
bin/build.sh        Deploy build — dependencies, CSS, collectstatic, migrate
bin/vendor-js.mjs   Copies third-party browser JS out of node_modules
```

## Where the seam falls

The one architectural decision worth reading before anything else.

PRD §8 asks for phase transitions under 200ms and a session that survives the
venue wifi dropping between Look and Smell. A request per tap delivers
neither. So the app is split:

- **The guided session** (`/taste/`) is one page and a client-side state
  machine. It fetches the lexicon once, caches it in IndexedDB, and then runs
  the whole tasting locally — every tap is written to IndexedDB before
  anything is sent, and the network is a background sync that catches up.
  This is the one part of the site that needs JavaScript.
- **Everything else** — the journal, sign-in — is ordinary server-rendered
  HTML with HTMX, and works with scripting off.

The rules of the session live in `static/js/session/session_core.js`, with no
DOM, no storage and no network, so they can be unit-tested directly. The other
modules are the thin layers around it.

## Styling

Tailwind v4, compiled by its CLI. There is no `tailwind.config.js` — v4 is
configured in CSS, and [src/css/main.css](src/css/main.css) is both the entry
point and the single source of design tokens.

Two rules:

- **No arbitrary values in templates.** `text-[13px]` hard-codes a decision
  where a token would record one. If a size is missing from the scale, add it
  to `@theme` and give it a name.
- **No `dark:` variants.** The palette flips at the variable level — `@theme`
  holds the light values, and a `prefers-color-scheme` block plus two
  `[data-theme]` blocks reassign them. Utilities generated from `@theme`
  reference the variables rather than inlining them, so `bg-paper` is already
  correct in both themes. The explicit `[data-theme]` blocks come last so a
  reader's manual choice beats their OS preference in either direction.

`static/css/output.css` is a build artefact and is not committed. Every path
that serves it builds it first: `npm run build:css` locally, `commands_pre` in
the e2e tox env, and `bin/build.sh` on deploy.

## How the front end works

There is no bundler and no CDN. The browser loads exactly the files in
`static/`, and `htmx.min.js` is committed there — `bin/vendor-js.mjs` copies it
out of `node_modules` so npm pins the version while the served file stays
visible in diffs. To update it:

```bash
npm install htmx.org@latest && npm run vendor
```

The theme toggle is rendered `hidden` and revealed by `theme.js` — a control
that cannot work without JS should not be visible before JS runs. An inline
script in `<head>` applies the stored theme before first paint, so a
dark-theme reader never sees a white flash.

The service worker stands down entirely under `DEBUG`. Its cache version is
derived from the release version, which is the constant `"dev"` locally, so
cache-first on `/static/` would serve an edited module forever with nothing on
screen to say why.

## Testing

Three suites, three jobs:

- **pytest** (`tests/`) — models, views, the API, template rendering. This is
  where most tests belong; it has a 90% coverage floor.
- **Vitest** (`tests/js/`) — the client-side modules. Logic lives in
  `theme_core.js` and is tested directly; `theme.js` is the thin DOM wiring
  and is tested against a built DOM.
- **Playwright** (`tests/e2e/`) — only what genuinely needs a browser: the
  HTMX swap, the no-JavaScript path, and the theme toggle surviving a reload.
  Not in the default tox list, because it is slow.

## CI

| Workflow | Jobs |
| --- | --- |
| `ci.yml` | Static analysis matrix (fmt, lint, djangofmt, mypy), Django checks, tests |
| `js.yml` | Vitest |
| `e2e.yml` | Playwright |
| `security-audit.yml` | pip-audit (runtime), pip-audit + npm audit (dev, detection only), semgrep, gitleaks — plus a weekly cron |

Two conventions worth knowing before editing a workflow:

- **No path filters on triggers.** A path-filtered required check never
  reports on commits outside its paths, and the PR sits at "Expected" forever.
- **`Security audit` is the release gate and is scoped to `--no-dev`.** An
  advisory in a linter must never be able to block a production release. The
  dev-group and npm coverage lives in `Dependency audit (dev + npm)`, which is
  loud but not required.

## Deployment

Build with [bin/build.sh](bin/build.sh) — it installs runtime dependencies
from `uv.lock`, compiles the stylesheet, runs `collectstatic` and applies
migrations. The Tailwind step is not optional: `output.css` is gitignored, so
a fresh checkout does not have it, and `collectstatic` under
`ManifestStaticFilesStorage` fails on a `{% static %}` reference it cannot
resolve.

`config.settings.production` expects `SECRET_KEY`, `ALLOWED_HOSTS` and
`DATABASE_URL`, serves static files through WhiteNoise, and turns on the usual
HSTS / secure-cookie / SSL-redirect settings. Run it under gunicorn against
`config.wsgi:application`.
