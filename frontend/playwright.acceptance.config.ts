import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./acceptance",
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: { baseURL: "http://127.0.0.3:5176", trace: "retain-on-failure" },
  webServer: [
    {
      command:
        process.platform === "win32"
          ? ".venv\\Scripts\\python.exe -B -m scripts.acceptance_server"
          : "python -B -m scripts.acceptance_server",
      cwd: "..",
      url: "http://127.0.0.3:8012/health",
      timeout: 180_000,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --host 127.0.0.3 --port 5176 --strictPort",
      url: "http://127.0.0.3:5176",
      env: { VITE_API_URL: "http://127.0.0.3:8012" },
      reuseExistingServer: false,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
