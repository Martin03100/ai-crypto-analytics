/** Vite configuration. */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Read-only API responses the app may show while offline (the last copy seen online).
// Anything with secrets or side effects (API keys, activity log, exports, all writes) is never cached.
const OFFLINE_API = /^\/api\/(account\/watchlist|schedules|forecast\/(history(?!\/export)|leaderboard)|portfolio\/history|market\/(fear-greed|headlines|prices|chart|events|onchain|vote\/percentages))(\/|\?|$)/;

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "prompt",           // the app asks before switching to a new version
      injectRegister: false,             // registered from src/pwa.js (no inline script, CSP stays strict)
      manifest: false,                   // public/manifest.json is used as is
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        // Not needed to start the app offline: optional monitoring SDK, rare font subsets, share images.
        globIgnores: ["**/vendor_sentry-*.js", "**/*-{cyrillic,greek,vietnamese}*.woff2", "**/og-image.png", "**/icon-512.png"],
        navigateFallback: "/index.html",
        importScripts: ["/push-sw.js"],      // Web Push: show notifications and open the app on click
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            urlPattern: ({ url, sameOrigin }) => sameOrigin && url.pathname.startsWith("/assets/") && url.pathname.endsWith(".woff2"),
            handler: "CacheFirst",
            options: { cacheName: "fonts", expiration: { maxEntries: 20 } },
          },
          {
            // Workbox copies this function into sw.js as text, so the pattern must be written inline
            // (it is the same literal as OFFLINE_API above; src/__tests__/pwaCache.test.js checks both stay equal).
            urlPattern: ({ url, request, sameOrigin }) =>
              sameOrigin && request.method === "GET" && /^\/api\/(account\/watchlist|schedules|forecast\/(history(?!\/export)|leaderboard)|portfolio\/history|market\/(fear-greed|headlines|prices|chart|events|onchain|vote\/percentages))(\/|\?|$)/.test(url.pathname + url.search),
            handler: "NetworkFirst",
            options: {
              cacheName: "api-data",
              networkTimeoutSeconds: 8,
              expiration: { maxEntries: 120, maxAgeSeconds: 24 * 3600 },   // matches the offline session window
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  test: {
    environment: "node",
    globals: false,
    // Playwright end-to-end specs in e2e/ run with `npm run test:e2e`, not with Vitest.
    include: ["src/**/*.test.{js,jsx}"],
    setupFiles: ["src/testSetup.js"],
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Fonts are never inlined as data: URLs: the production CSP allows fonts only from 'self'.
    assetsInlineLimit: (file) => (/\.(woff2?|ttf|otf)$/.test(file) ? false : undefined),
    rolldownOptions: {
      output: {
        // Rolldown code-splitting groups (higher priority wins). React must stay in its own chunk: with the old
        // manualChunks emulation it ended up inside the chart chunk and every page downloaded Recharts.
        codeSplitting: {
          groups: [
            { name: "vendor_react", test: /[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler|react-is|use-sync-external-store)[\\/]/, priority: 40 },
            { name: "vendor_sentry", test: /[\\/]node_modules[\\/]@sentry/, priority: 30 },
            { name: "vendor_icons", test: /[\\/]node_modules[\\/]lucide-react[\\/]/, priority: 30 },
            { name: "vendor_charts", test: /[\\/]node_modules[\\/](recharts|d3-[^\\/]+|victory-vendor|internmap|decimal\.js-light|eventemitter3|lodash)[\\/]/, priority: 20 },
          ],
        },
      },
    },
  },
});
