import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', timeout: 30_000, fullyParallel: true, workers: 2,
  outputDir: process.env.ALBUM_LIVE_FIXTURES ? 'test-results/live' : 'test-results/browser',
  reporter: [['list'], ['html', { open: 'never', outputFolder: process.env.ALBUM_LIVE_FIXTURES ? 'playwright-report/live' : 'playwright-report/browser' }]],
  use: {
    baseURL: process.env.ALBUM_BASE_URL || 'http://127.0.0.1:4173',
    locale: 'en-GB', reducedMotion: 'reduce',
    launchOptions: process.env.PLAYWRIGHT_EXECUTABLE_PATH ? {executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH, args: ['--no-sandbox']} : {},
    screenshot: 'only-on-failure', trace: 'retain-on-failure',
  },
  webServer: process.env.ALBUM_BASE_URL ? undefined : {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173', reuseExistingServer: !process.env.CI,
  },
});
