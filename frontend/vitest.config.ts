import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.tsx"],
    include: ["**/__tests__/**/*.{test,spec}.{ts,tsx}"],
    exclude: [
      "node_modules",
      ".next",
      "e2e", // Playwright E2E tests have their own runner
    ],
    // Increase timeout for async React 19 rendering
    testTimeout: 10000,
    // CSS modules and static assets should not break tests
    css: false,
  },
  resolve: {
    alias: {
      // Match tsconfig.json paths: "@/*" -> "./*"
      "@": path.resolve(__dirname, "."),
    },
  },
});
