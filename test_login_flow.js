import { chromium } from '@playwright/test';

(async () => {
  console.log("Launching Edge browser...");
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Monitor network requests
  page.on('request', request => {
    if (request.url().includes('login') || request.url().includes('auth')) {
      console.log('Request:', request.method(), request.url());
    }
  });

  page.on('response', response => {
    if (response.url().includes('login') || response.url().includes('auth')) {
      console.log('Response:', response.status(), response.url());
      response.text().then(text => console.log('Response Body:', text.slice(0, 300))).catch(() => {});
    }
  });

  console.log("Navigating to login page...");
  await page.goto('https://calle-healthcare-os.vercel.app/login');
  await page.waitForTimeout(3000);

  console.log("Filling credentials...");
  await page.fill('input[type="email"]', 'admin@callehealthcare.com');
  await page.fill('input[type="password"]', 'Admin@12345!');

  console.log("Clicking Sign In...");
  await page.click('button[type="submit"]');

  await page.waitForTimeout(8000);
  console.log("Current URL after login:", page.url());

  const localStorage = await page.evaluate(() => JSON.stringify(window.localStorage));
  console.log("localStorage keys:", Object.keys(JSON.parse(localStorage)));

  await browser.close();
})().catch(err => {
  console.error("E2E Login Test Failed:", err);
  process.exit(1);
});
