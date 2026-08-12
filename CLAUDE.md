# CLAUDE.md

Project conventions. Read [README.md](README.md) first for setup and commands.

## Stack

Django 6 + HTMX, Tailwind v4 for styling, everything else served straight from
`static/` — no bundler, no CDN. Python 3.14, managed with uv. `tox` is the
entrypoint for every check; CI runs the same envs, so a green `tox` locally
means a green CI.

## Invariants

1. **Every check runs through tox.** Do not add a CI step that invokes
   pytest / ruff / mypy directly — add a tox env and call that, so local and
   CI cannot drift.
2. **One version of each tool.** ruff is pinned exactly in `pyproject.toml`'s
   `lint` group and must match `.pre-commit-config.yaml`'s rev. Bump both in
   the same commit.
3. **Every interactive element works without JavaScript.** JS enhances; it is
   never the only way to do something. A control that cannot work without JS
   is rendered `hidden` and revealed by the script that makes it work.
4. **No secrets in source.** Configuration comes from the environment via
   python-decouple. gitleaks runs in pre-commit and in CI.
5. **No hard-coded external hostnames or endpoints.** They belong in settings,
   read from the environment, with the current value as the default.
6. **Coverage floor is 90%** on `apps/` and `config/`. Modules only a deployed
   process imports (`production.py`, `wsgi.py`) are omitted, not exempted by
   lowering the bar.
7. **Design decisions live in `src/css/main.css`, not in templates.** No
   arbitrary Tailwind values (`text-[13px]`, `bg-[#7b1e3c]`) and no `dark:`
   variants — see Styling below.

## Where things go

- `apps/public/` — the public site. New pages go here until there is a reason
  to split an app out.
- `config/settings/` — `base.py` holds everything environment-agnostic;
  `development.py` and `production.py` override. Never put a secret in any of
  them.
- `templates/` — site-wide. `base.html` and `includes/`.
- `apps/*/templates/<app>/` — page and fragment templates for that app.
  Fragments are prefixed with an underscore.
- `src/css/main.css` — the Tailwind entry point and every design token. There
  is no `tailwind.config.js`; v4 is configured in CSS.
- `static/css/output.css` — build output, gitignored. Never edit it, and never
  commit it.
- `static/js/` — one module per concern. Logic that can be tested without a
  DOM goes in a `*_core.js` module; the sibling module does the DOM wiring.
  Third-party JS is vendored by `bin/vendor-js.mjs` and committed.

## Styling

Tailwind utilities in templates, tokens in `src/css/main.css`. Two rules, both
of which exist so that a visual decision is recorded in one place:

- **No arbitrary values in templates.** `text-[13px]` states a size without
  saying what it is for. Add a named token to `@theme` instead — the scale
  already carries `text-display`, `text-body`, `text-fact`, `text-caption`,
  `text-meta`.
- **No `dark:` variants.** The palette flips at the variable level: `@theme`
  holds the light values, and a `prefers-color-scheme` block plus two
  `[data-theme]` blocks reassign them. Utilities generated from `@theme`
  reference the variables rather than inlining them, so `bg-paper` is already
  correct in both themes. Reach for `dark:` and you have created a second
  place where the theme is decided.

`@theme static` is deliberate: without it, Tailwind emits only the variables
some utility currently references, and a token given a dark value but no
utility yet would resolve to nothing.

Everything that serves the stylesheet builds it first — `npm run build:css`,
`commands_pre` in the e2e tox env, `bin/build.sh` on deploy. A rule that
cannot be a utility (an htmx runtime state, a third-party override) goes in
the components layer at the bottom of `main.css`, with a comment saying why.

## Testing

Reach for the cheapest suite that can prove the thing:

- **pytest** for views, templates and data. Most tests belong here.
- **Vitest** (`tests/js/`) for client-side logic. Prefer testing the `_core`
  module directly over building a DOM.
- **Playwright** (`tests/e2e/`) only for what needs a real browser — the HTMX
  swap, the no-JS path, theme persistence across a reload. Keep this suite
  small; it is the slowest thing in CI and the first to go flaky.

An HTMX view has two response shapes. Test both: `HX-Request: true` gets the
fragment, a plain request gets the whole page. The `htmx_client` fixture in
`tests/conftest.py` is the first of those.

## Templates

- `djangofmt` formats them, enforced by `tox -e djangofmt` (which formats in
  place and then fails on any diff — so run it before pushing).
- Page identity is set in one place: a page's `{% block page_meta %}`
  includes `includes/_page_meta.html` with `title` and `description`. Do not
  add a separate title block; one emitter means a page cannot half-set its
  metadata.
- All user-facing copy goes through `{% translate %}` / `{% blocktranslate %}`.

## CI

- Workflow triggers are deliberately not path-filtered. A path-filtered
  required check never reports on commits outside its paths, and the PR sits
  at "Expected" forever.
- Third-party actions are pinned to commit SHAs with a version comment;
  Dependabot updates both.
- `Security audit` (`--no-dev`) is the release gate. `Dependency audit
  (dev + npm)` is detection-only and must not become a required check — an
  advisory in a linter should be visible without being able to block a
  release.
- Every ignored advisory in `tox.ini` carries a reason and a removal
  condition. An ignore with no exit criterion turns a red check into noise.

## Commits

Claude commits as itself, with Hugo as committer:

```bash
git commit --author="Claude <noreply@anthropic.com>" -m "subject"
```
