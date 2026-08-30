import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', msg => console.log('[CONSOLE]', msg.text()));
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message));
  
  page.on('request', req => {
    if (req.url().includes('/auth')) {
      console.log('>> REQ:', req.method(), req.url());
    }
  });

  page.on('response', async res => {
    if (res.url().includes('/auth')) {
      let body = '';
      try { body = await res.text(); } catch (e) {}
      console.log('<< RES:', res.status(), res.url(), body.slice(0, 150));
    }
  });

  console.log('Navigating to login...');
  await page.goto('https://calle-healthcare-os.vercel.app/login');
  await page.fill('input[type="email"]', 'admin@callehealthcare.com');
  await page.fill('input[type="password"]', 'Admin@12345!');

  console.log('Clicking sign in...');
  await page.click('button[type="submit"]');

  await page.waitForTimeout(10000);
  console.log('Final URL:', page.url());

  await browser.close();
})();
