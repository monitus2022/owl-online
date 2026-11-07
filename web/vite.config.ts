import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Port 5500 matches the API's default CORS allowlist (app/config.py), so the
// dev server talks to a local uvicorn without extra configuration.
export default defineConfig({
  plugins: [react()],
  server: { port: 5500, strictPort: true },
  build: { target: "es2022" },
});
