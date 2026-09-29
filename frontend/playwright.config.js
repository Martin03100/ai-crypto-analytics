/** End-to-end tests: start the real backend (fresh SQLite DB) and the Vite dev server, then drive Chromium. */

import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const python = process.env.E2E_PYTHON || "python";
const dbFile = path.join(os.tmpdir(), `aca-e2e-${Date.now()}.db`).replace(/\\/g, "/");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // Optional: reuse an already installed Chromium instead of `npx playwright install`.
    launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port 8000`,
      cwd: "../backend",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        DATABASE_URL: `sqlite:///${dbFile}`,
        APP_ENV: "development",
        JWT_SECRET_KEY: "e2e-only-jwt-secret-not-for-production-use",
        API_KEY_ENCRYPTION_SECRET: "e2e-only-fernet-secret-not-for-production",
        PASSWORD_HASH_ROUNDS: "1000",
        TURNSTILE_SECRET_KEY: "",
        BREVO_API_KEY: "",
        SMTP_HOST: "",
      },
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { VITE_TURNSTILE_SITE_KEY: "", VITE_SENTRY_DSN: "" },
    },
  ],
});
