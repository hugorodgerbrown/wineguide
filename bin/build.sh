#!/usr/bin/env bash
# bin/build.sh — Deploy build script.
#
# Runs on each deploy to install dependencies, build the Tailwind stylesheet,
# collect static files and apply migrations. The Tailwind step is not optional:
# static/css/output.css is gitignored, so it does not exist in a fresh
# checkout, and collectstatic under ManifestStaticFilesStorage fails on a
# {% static %} reference it cannot resolve.

set -o errexit

# Python dependencies. Keep the environment inside the project so this works on
# hosts that provide no active virtualenv. `--no-dev` installs runtime
# dependencies only; `--frozen` installs strictly from uv.lock and fails if it
# is out of date rather than silently re-resolving.
pip install uv
uv sync --no-dev --frozen

# Tailwind. `npm ci` rather than `npm install` so the build cannot drift from
# package-lock.json.
npm ci
npx @tailwindcss/cli -i ./src/css/main.css -o ./static/css/output.css --minify

uv run --no-sync python manage.py collectstatic --no-input
uv run --no-sync python manage.py migrate
