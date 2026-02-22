import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E test configuration for SIMS Plus frontend.
 *
 * Multi-tenant note: The app uses subdomain-based routing in production
 * ({school}.simsplus.io), but in dev/test mode the backend also supports
 * an X-Subdomain header for tenant resolution. E2E tests that need a
 * tenant context should set this header via page.setExtraHTTPHeaders() or
 * use the API directly with the X-Subdomain header. Tests that target the
 * main site (e.g. registration, login without tenant) can use baseURL directly.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "html",
  // Default timeout for each test (30 seconds)
  timeout: 30000,
  // Default expect timeout (5 seconds)
  expect: {
    timeout: 5000,
  },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    // Capture screenshot on failure for debugging
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    // Give the dev server time to start
    timeout: 120000,
  },
});
