import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import tseslint from 'typescript-eslint'
import eslintConfigPrettier from 'eslint-config-prettier'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Initial-data-fetch-on-mount is a pervasive pattern in this codebase;
      // the rule fires on every useEffect that calls an async setState helper.
      'react-hooks/set-state-in-effect': 'off',
      // Icon map lookups return stable references, not dynamically created components.
      'react-hooks/static-components': 'off',
      'no-console': ['error', { allow: ['warn', 'error'] }],
      // autoFocus is used intentionally on dialog/modal inputs for UX —
      // the a11y concern is about page-level autofocus, not scoped modals.
      'jsx-a11y/no-autofocus': 'off',
    },
  },
  eslintConfigPrettier,
])
