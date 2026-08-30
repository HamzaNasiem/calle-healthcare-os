import { chromium } from '@playwright/test';
import path from 'path';

(async () => {
  console.log('======================================================================');
  console.log('  BYTELYTIC CLINIC OS — FULL SUITE REAL BROWSER PRODUCTION AUDIT');
  console.log('======================================================================\n');

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('[BROWSER ERROR]', msg.text());
      errors.push(msg.text());
    }
  });
  page.on('pageerror', err => {
    console.error('[PAGE EXCEPTION]', err.message);
    errors.push(err.message);
  });

  const ARTIFACTS_DIR = 'C:\\Users\\LENOVO\\.gemini\\antigravity\\brain\\5d0d71c7-dbf1-410f-b027-37d004e0b4ee';

  // 1. LOGIN
  console.log('>>> 1. NAVIGATING TO LOGIN & AUTHENTICATING REAL USER');
  await page.goto('https://calle-healthcare-os.vercel.app/login', { waitUntil: 'networkidle' });
  await page.fill('input[type="email"]', 'admin@callehealthcare.com');
  await page.fill('input[type="password"]', 'Admin@12345!');
  await page.click('button[type="submit"]');

  // Wait for redirect to /
  await page.waitForURL('https://calle-healthcare-os.vercel.app/', { timeout: 20000 });
  console.log('[OK] Logged in successfully. Current URL:', page.url());

  // Wait for dashboard data to hydrate
  await page.waitForTimeout(5000);
  const dashPath = path.join(ARTIFACTS_DIR, 'page_1_dashboard.png');
  await page.screenshot({ path: dashPath, fullPage: true });
  console.log('[OK] Captured Dashboard Screenshot:', dashPath);

  // 2. APPOINTMENTS
  console.log('\n>>> 2. NAVIGATING TO APPOINTMENTS');
  await page.goto('https://calle-healthcare-os.vercel.app/appointments', { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);
  const apptPath = path.join(ARTIFACTS_DIR, 'page_2_appointments.png');
  await page.screenshot({ path: apptPath, fullPage: true });
  const apptText = await page.textContent('body');
  console.log('[OK] Captured Appointments Screenshot. Text length:', apptText.length);

  // 3. PATIENTS
  console.log('\n>>> 3. NAVIGATING TO PATIENTS');
  await page.goto('https://calle-healthcare-os.vercel.app/patients', { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);
  const patPath = path.join(ARTIFACTS_DIR, 'page_3_patients.png');
  await page.screenshot({ path: patPath, fullPage: true });
  const patText = await page.textContent('body');
  console.log('[OK] Captured Patients Screenshot. Text length:', patText.length);

  // 4. OUTBOUND CAMPAIGNS
  console.log('\n>>> 4. NAVIGATING TO OUTBOUND CAMPAIGNS');
  await page.goto('https://calle-healthcare-os.vercel.app/outbound-campaigns', { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);
  const campPath = path.join(ARTIFACTS_DIR, 'page_4_campaigns.png');
  await page.screenshot({ path: campPath, fullPage: true });
  const campText = await page.textContent('body');
  console.log('[OK] Captured Campaigns Screenshot. Text length:', campText.length);

  // 5. PRIOR AUTH
  console.log('\n>>> 5. NAVIGATING TO PRIOR AUTH');
  await page.goto('https://calle-healthcare-os.vercel.app/prior-auth', { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);
  const authPath = path.join(ARTIFACTS_DIR, 'page_5_prior_auth.png');
  await page.screenshot({ path: authPath, fullPage: true });
  const authText = await page.textContent('body');
  console.log('[OK] Captured Prior Auth Screenshot. Text length:', authText.length);

  // 6. SETTINGS
  console.log('\n>>> 6. NAVIGATING TO SETTINGS');
  await page.goto('https://calle-healthcare-os.vercel.app/settings', { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);
  const setPath = path.join(ARTIFACTS_DIR, 'page_6_settings.png');
  await page.screenshot({ path: setPath, fullPage: true });
  const setText = await page.textContent('body');
  console.log('[OK] Captured Settings Screenshot. Text length:', setText.length);

  console.log('\n======================================================================');
  console.log(`AUDIT COMPLETE: 6 PAGES RENDERED | TOTAL CONSOLE/PAGE ERRORS: ${errors.length}`);
  console.log('======================================================================');

  await browser.close();
})().catch(err => {
  console.error('AUDIT FAILED:', err);
  process.exit(1);
});
