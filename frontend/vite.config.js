import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    globals: false,
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
    rollupOptions: {
      output: {
        // Rozdel velke, zriedka sa menajuce kniznice do vlastneho "vendor"
        // chunku oddeleneho od aplikacneho kodu. Vyhoda: ked appku
        // aktualizujes, prehliadac znovu stiahne len maly app.js chunk,
        // vendor.js (recharts, lucide-react...) ostane v cache prehliadaca
        // nezmeneny, kym sa nezmenia jeho verzie v package.json.
        manualChunks: {
          vendor_react: ["react", "react-dom", "react-router-dom"],
          vendor_charts: ["recharts"],
          vendor_icons: ["lucide-react"],
        },
      },
    },
  },
});
