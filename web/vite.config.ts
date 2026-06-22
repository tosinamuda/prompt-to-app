import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The backend (FastAPI: MCP + A2A + REST + /app) runs on 8011. Proxy same-origin so
// the A2A client, REST calls, and the generated-app iframe all share one origin.
const BACKEND = process.env.VITE_BACKEND ?? "http://127.0.0.1:8011";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5180,
    proxy: {
      "/a2a": { target: BACKEND, changeOrigin: true },
      "/mcp": { target: BACKEND, changeOrigin: true },
      "/api": { target: BACKEND, changeOrigin: true },
      "/app": { target: BACKEND, changeOrigin: true },
      "/static": { target: BACKEND, changeOrigin: true },
    },
  },
});
