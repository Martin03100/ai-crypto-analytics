import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";

export default [
  { ignores: ["dist", "playwright-report", "test-results"] },
  js.configs.recommended,
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      // Classic hook rules; the React Compiler rules (purity, set-state-in-effect, ...) do not apply to this app.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "react-refresh/only-export-components": ["warn", {
        allowConstantExport: true,
        allowExportNames: ["hasForecastSeries", "hasSeenOnboarding", "resetOnboarding"],
      }],
      "no-empty": ["error", { allowEmptyCatch: true }],  // storage access may throw (private mode); ignoring is intended
      // JSX usage is invisible to the core rule without eslint-plugin-react; ignore capitalised names.
      "no-unused-vars": ["error", { varsIgnorePattern: "^[A-Z_]", argsIgnorePattern: "^_" }],
    },
  },
  {
    // Context modules export their provider together with its hook, which is the intended pattern.
    files: ["src/context/**"],
    rules: { "react-refresh/only-export-components": "off" },
  },
  {
    files: ["**/__tests__/**", "e2e/**", "*.config.js"],
    languageOptions: { globals: { ...globals.node } },
  },
];
