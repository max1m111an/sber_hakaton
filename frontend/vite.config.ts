import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from "node:path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // В dev-режиме запросы к API проксируются на локально запущенный FastAPI
    proxy: {
      "/api": process.env.VITE_PROXY_TARGET ?? "http://localhost:8080",
      "/openapi.json": process.env.VITE_PROXY_TARGET ?? "http://localhost:8080",
    },
  },
})
