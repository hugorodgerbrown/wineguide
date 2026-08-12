// vitest.config.mjs — Configuration for the JS unit-test harness.
//
// `include` overrides Vitest's default glob (which requires a `.test.` or
// `.spec.` infix) so JS tests can use the same `test_*` naming as the Python
// and Playwright suites.
//
// No coverage config: the coverage target in this project is Python-only.

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/js/setup.js'],
    include: ['tests/js/**/test_*.js'],
  },
});
