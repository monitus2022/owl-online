import { defineConfig } from "@playwright/test";

// The E2E suite runs the real FastAPI app with an injected stub runtime and
// the real Vite frontend. The corpus, index and pack prose stay out of git.
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:5500",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "uv run python e2e/api_server.py",
      url: "http://127.0.0.1:8001/health",
      cwd: "..",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm --prefix web run dev -- --host 127.0.0.1 --port 5500",
      url: "http://127.0.0.1:5500",
      cwd: "..",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: { VITE_OWL_API_BASE: "http://127.0.0.1:8001" },
    },
  ],
});
