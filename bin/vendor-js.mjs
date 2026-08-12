/*
 * bin/vendor-js.mjs — Copy third-party browser JS out of node_modules into
 * static/js/, where Django serves it.
 *
 * The copies ARE committed. The site has no bundler and no CDN dependency, so
 * the file the browser loads is a file in the repository, visible in diffs and
 * covered by the same review as everything else. They land under
 * static/js/vendor/, which the whitespace pre-commit hooks skip — otherwise
 * every refresh would be followed by a hook rewriting the file. npm is here
 * only to pin the version and make refreshing it one command:
 *
 *     npm install htmx.org@latest && npm run vendor
 *
 * Run from the project root.
 */

import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

const ASSETS = [['htmx.org/dist/htmx.min.js', 'static/js/vendor/htmx.min.js']];

mkdirSync(join(ROOT, 'static/js/vendor'), { recursive: true });

for (const [from, to] of ASSETS) {
  copyFileSync(join(ROOT, 'node_modules', from), join(ROOT, to));
  process.stdout.write(`${to}\n`);
}
