import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
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
    },
  },
])
