import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { visualizer } from "rollup-plugin-visualizer"

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(process.env.ANALYZE === "true"
      ? [visualizer({ open: true, gzipSize: true, filename: "dist/bundle-stats.html" })]
      : []),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    // Disable the inline module-preload polyfill so a strict CSP
    // (script-src 'self') doesn't block it. If nonce-based CSP is deployed,
    // set html.cspNonce instead and re-enable the polyfill.
    modulePreload: { polyfill: false },
    // Always wipe the output directory before building so stale hashed
    // bundles from prior builds are not left in app/static/assets/.
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Three.js is large (~600 KB min) and only used by the visualization
          // tab (lazy-loaded). Splitting it into its own chunk avoids bloating
          // the main vendor bundle for users who never open that tab.
          "vendor-three": ["three"],
        },
      },
    },
  },
  server: {
    port: parseInt(process.env.FRONTEND_PORT || "9714"),
    proxy: {
      "/api": {
        target: `http://localhost:${process.env.API_PORT || "9713"}`,
        changeOrigin: true,
      },
    },
  },
})
