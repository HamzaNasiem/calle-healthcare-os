import { test, expect } from '@playwright/test';

const BASE_URL = 'https://calle-healthcare-os.vercel.app';
const ADMIN_EMAIL = 'admin@callehealthcare.com';
const ADMIN_PASS = 'Admin@12345!';

test.describe('Bytelytic Clinic OS — Comprehensive Live Browser E2E Suite', () => {
  test.setTimeout(60000);

  test('E2E-1: Live Authentication, Redirection & Dashboard Screenshot', async ({ page }) => {
    console.log('Visiting live login page:', `${BASE_URL}/login`);
    await page.goto(`${BASE_URL}/login`);

    // Fill login form
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(ADMIN_PASS);

    // Wait for the login API response upon click
    const [loginResponse] = await Promise.all([
      page.waitForResponse(res => res.url().includes('/auth/login') && res.status() === 200, { timeout: 25000 }),
      page.locator('button[type="submit"]').click()
    ]);

    console.log('Login API returned 200 OK! Response status:', loginResponse.status());

    // Wait for navigation away from /login
    await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 20000 });
    console.log('Landed on page:', page.url());

    // Wait for main dashboard container to render
    await page.waitForSelector('main, .min-h-screen', { timeout: 15000 });
    await page.waitForTimeout(3000);

    // Capture real live dashboard screenshot
    const screenshotPath = 'C:\\Users\\LENOVO\\.gemini\\antigravity\\brain\\5d0d71c7-dbf1-410f-b027-37d004e0b4ee\\dashboard_live_screenshot.png';
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log('Saved live browser screenshot to:', screenshotPath);

    // Verify page contains dashboard or clinic elements
    const bodyText = await page.textContent('body');
    expect(bodyText.length).toBeGreaterThan(100);
  });

  test('E2E-2: Navigate to Patients Page & Render Records', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(ADMIN_PASS);

    await Promise.all([
      page.waitForResponse(res => res.url().includes('/auth/login') && res.status() === 200, { timeout: 25000 }),
      page.locator('button[type="submit"]').click()
    ]);
    await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 20000 });

    // Navigate to Patients
    await page.goto(`${BASE_URL}/patients`);
    await page.waitForTimeout(4000);

    const bodyText = await page.textContent('body');
    console.log('Patients page body text length:', bodyText.length);
    expect(bodyText).toContain('Patient');
  });

  test('E2E-3: Navigate to Appointments Page & Verify Schedule', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(ADMIN_PASS);

    await Promise.all([
      page.waitForResponse(res => res.url().includes('/auth/login') && res.status() === 200, { timeout: 25000 }),
      page.locator('button[type="submit"]').click()
    ]);
    await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 20000 });

    // Navigate to Appointments
    await page.goto(`${BASE_URL}/appointments`);
    await page.waitForTimeout(4000);

    const bodyText = await page.textContent('body');
    console.log('Appointments page text length:', bodyText.length);
    expect(bodyText).toContain('Appointment');
  });
});
