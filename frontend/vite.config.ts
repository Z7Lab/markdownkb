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
