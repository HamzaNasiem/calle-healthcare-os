import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/live_clinic_os.spec.js',
  timeout: 45000,
  expect: {
    timeout: 10000
  },
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'https://calle-healthcare-os.vercel.app',
    channel: 'msedge',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
