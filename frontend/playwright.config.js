import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  timeout: 180000,
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
  },
})
