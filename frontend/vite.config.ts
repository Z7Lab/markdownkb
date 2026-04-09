import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
