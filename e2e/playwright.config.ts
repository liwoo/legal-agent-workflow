import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the Contract Triage end-to-end walkthrough.
 *
 * The test drives the *already-running* stack (frontend :3000 + API :8000 +
 * Langfuse :3001) — it does not start it. Bring the stack up first (see the
 * tester how-to guide / e2e/README), then run `npm test` from this folder.
 *
 * Triage is a real LLM call, so timeouts are generous. Screenshots for every
 * stage of the walkthrough are written to e2e/artifacts/.
 */
export default defineConfig({
  testDir: "./tests",
  outputDir: "./artifacts/test-results",
  fullyParallel: false,
  workers: 1,
  timeout: 180_000, // a full triage run can take 30-60s
  expect: { timeout: 60_000 },
  reporter: [
    ["list"],
    ["html", { outputFolder: "./artifacts/html-report", open: "never" }],
  ],
  use: {
    baseURL: process.env.FRONTEND_URL ?? "http://localhost:3000",
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
