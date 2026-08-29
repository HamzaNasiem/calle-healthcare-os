import { test, expect } from '@playwright/test';

test.describe('Clinic OS End-to-End Suite', () => {
  test.beforeEach(async ({ page }) => {
    // Open the login page
    await page.goto('http://localhost:5173/login');
  });

  test('should log in successfully and redirect to dashboard', async ({ page }) => {
    // Fill credentials
    await page.fill('input[type="email"]', 'qa_admin_tester@gmail.com');
    await page.fill('input[type="password"]', 'SecurePass123!');
    
    // Click Sign In
    await page.click('button[type="submit"]');

    // Should navigate to dashboard
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('text=Bytelytic Clinic OS')).toBeVisible();
  });

  test('should navigate to setup/settings page and update clinic info', async ({ page }) => {
    // Login first
    await page.fill('input[type="email"]', 'qa_admin_tester@gmail.com');
    await page.fill('input[type="password"]', 'SecurePass123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/.*dashboard/);

    // Open settings via avatar/nav
    await page.click('a[href="/setup"]');
    await expect(page).toHaveURL(/.*setup/);

    // Edit clinic name
    await page.fill('input[name="clinicName"]', 'Updated QA Clinic Name');
    await page.click('button:has-text("Save Changes")');

    // Verify confirmation message
    await expect(page.locator('text=Changes saved successfully')).toBeVisible();
  });
});
