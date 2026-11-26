import js from '@eslint/js';
import { defineConfig, globalIgnores } from 'eslint/config';
import prettier from 'eslint-config-prettier';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig(
  globalIgnores(['**/node_modules/**', '**/dist/**', '**/*.d.ts', '.venv/**', '.turbo/**']),
  {
    files: ['tooling/**/*.mjs', 'packages/tokens/build.mjs', 'eslint.config.mjs'],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['apps/web/**/*.{ts,tsx}', 'packages/*/src/**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: { '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }] },
  },
  {
    files: ['apps/web/src/**/*.{ts,tsx}', 'packages/{ui,media}/src/**/*.{ts,tsx}'],
    extends: [reactHooks.configs.flat.recommended],
    rules: { 'react-hooks/exhaustive-deps': 'error' },
  },
  prettier,
);
