import { defineConfig } from '@playwright/test'
import * as dotenv from 'dotenv'

dotenv.config()

const webBase = process.env.RG_WEB_BASE || 'http://localhost:5173'
const apiBase = process.env.RG_API_BASE || 'http://localhost:8080'
process.env.RG_API_BASE = apiBase

export default defineConfig({
  testDir: './tests',
  timeout: 180_000,
  expect: {
    timeout: 15_000,
  },
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: webBase,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  reporter: [['list']],
  metadata: {
    RG_API_BASE: apiBase,
  },
})
