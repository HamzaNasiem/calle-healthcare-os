import { chromium } from '@playwright/test';

(async () => {
  console.log('>>> LAUNCHING REAL HEADLESS EDGE BROWSER');
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  const consoleLogs = [];
  const pageErrors = [];

  page.on('console', msg => {
    const text = msg.text();
    consoleLogs.push(text);
    console.log('[BROWSER CONSOLE]', text.slice(0, 140));
  });

  page.on('pageerror', err => {
    pageErrors.push(err.message);
    console.error('[BROWSER EXCEPTION]', err.message);
  });

  console.log('>>> STEP 1: Navigating to https://calle-healthcare-os.vercel.app/login');
  await page.goto('https://calle-healthcare-os.vercel.app/login', { waitUntil: 'networkidle', timeout: 30000 });

  console.log('>>> STEP 2: Filling real credentials for admin@callehealthcare.com');
  await page.fill('input[type="email"]', 'admin@callehealthcare.com');
  await page.fill('input[type="password"]', 'Admin@12345!');

  console.log('>>> STEP 3: Submitting login form');
  await page.click('button[type="submit"]');

  console.log('>>> STEP 4: Waiting 6 seconds for token storage, websocket handshake & dashboard load');
  await page.waitForTimeout(6000);

  console.log('>>> Current URL:', page.url());
  const bodyText = await page.textContent('body');
  console.log('>>> Body length:', bodyText.length);

  const screenshotPath = 'C:\\Users\\LENOVO\\.gemini\\antigravity\\brain\\5d0d71c7-dbf1-410f-b027-37d004e0b4ee\\real_dashboard_render.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('>>> SAVED REAL SCREENSHOT TO:', screenshotPath);

  // Navigate to Appointments
  console.log('>>> STEP 5: Navigating to Appointments page');
  await page.goto('https://calle-healthcare-os.vercel.app/appointments', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);

  const apptScreenshot = 'C:\\Users\\LENOVO\\.gemini\\antigravity\\brain\\5d0d71c7-dbf1-410f-b027-37d004e0b4ee\\real_appointments_render.png';
  await page.screenshot({ path: apptScreenshot, fullPage: true });
  console.log('>>> SAVED APPOINTMENTS SCREENSHOT TO:', apptScreenshot);

  // Navigate to Patients
  console.log('>>> STEP 6: Navigating to Patients page');
  await page.goto('https://calle-healthcare-os.vercel.app/patients', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);

  const patientsScreenshot = 'C:\\Users\\LENOVO\\.gemini\\antigravity\\brain\\5d0d71c7-dbf1-410f-b027-37d004e0b4ee\\real_patients_render.png';
  await page.screenshot({ path: patientsScreenshot, fullPage: true });
  console.log('>>> SAVED PATIENTS SCREENSHOT TO:', patientsScreenshot);

  console.log('>>> TOTAL BROWSER PAGE ERRORS:', pageErrors.length);
  if (pageErrors.length > 0) {
    console.log('Errors:', pageErrors);
  }

  await browser.close();
  console.log('>>> TEST SUITE COMPLETED SUCCESSFULLY');
})().catch(err => {
  console.error('CRITICAL TEST ERROR:', err);
  process.exit(1);
});
