# wineguide

A short, opinionated wine guide. Django + HTMX on the server, Tailwind for
styling, vanilla JS for progressive enhancement.

Right now it is a homepage: a hero, one wine pick, and a control that fetches
the next one.

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
apps/public/        The public site: views, URLs, templates, the wine data
config/             Settings (base / development / production), URLs, WSGI
templates/          Site-wide templates — base.html and its includes
src/css/main.css    Tailwind entry point and every design token
static/css/         Build output (output.css, gitignored)
static/js/          theme.js + theme_core.js
static/js/vendor/   Third-party JS, copied from node_modules and committed
tests/public/       pytest — views, templates, data
tests/js/           Vitest — the client-side modules
tests/e2e/          Playwright — the paths that need a real browser
bin/build.sh        Deploy build — dependencies, CSS, collectstatic, migrate
bin/vendor-js.mjs   Copies third-party browser JS out of node_modules
```

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

Both interactive elements work without JavaScript, and are better with it:

- **The wine picker** is an ordinary link to `/pick/?index=N`. HTMX intercepts
  it and swaps `#wine-panel` in place; without HTMX the browser follows the
  href and the same view returns the whole page.
- **The theme toggle** is rendered `hidden` and revealed by `theme.js`. A
  control that cannot work without JS should not be visible before JS runs.
  An inline script in `<head>` applies the stored theme before first paint so
  a dark-theme reader never sees a white flash.

## Testing

Three suites, three jobs:

- **pytest** (`tests/`) — views, template rendering, the data module. This is
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
