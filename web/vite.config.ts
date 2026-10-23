/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // In development the API runs on :8000; proxy it so the browser sees one origin (no CORS needed).
  const api = loadEnv(mode, ".", "").VITE_API_PROXY || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": api, "/health": api, "/ready": api, "/docs": api, "/openapi.json": api },
    },
    test: { environment: "node" },
  };
});
