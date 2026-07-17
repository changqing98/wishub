import { defineConfig, devices } from "@playwright/test";

const frontendUrl = "http://127.0.0.1:5173";
const backendUrl = "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [["list"]],
  use: {
    baseURL: frontendUrl,
    trace: "on-first-retry",
  },
  webServer: [
    {
      command:
        "cd .. && rm -f /tmp/wishub_playwright.sqlite3 && rm -rf /tmp/wishub_playwright_uploads /tmp/wishub_playwright_chroma && WISHUB_SQLITE_PATH=/tmp/wishub_playwright.sqlite3 WISHUB_UPLOAD_DIR=/tmp/wishub_playwright_uploads WISHUB_CHROMA_PATH=/tmp/wishub_playwright_chroma ANONYMIZED_TELEMETRY=False uv run --package backend uvicorn backend.main:app --host 127.0.0.1 --port 8000",
      url: `${backendUrl}/api/v1/knowledge-base/summary`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
