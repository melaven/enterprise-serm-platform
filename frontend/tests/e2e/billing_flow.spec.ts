/**
 * E2E Test: Billing Quota Enforcement & Paywall Flow
 * 
 * Scenario:
 * 1. User exhausts 5 free parser runs
 * 2. 6th parser attempt returns 402 Payment Required
 * 3. PaywallModal appears automatically
 * 4. User clicks "Upgrade to Pro"
 * 5. Redirects to Stripe Checkout
 * 
 * @requires Backend running on http://localhost:8000
 * @requires Frontend running on http://localhost:3000
 * @requires Test user with valid JWT token
 */

import { test, expect } from '@playwright/test';

// Test configuration
const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:3000';

// Test user credentials
const TEST_USER = {
  email: 'test@example.com',
  password: 'TestPassword123!',
};

// Mock parser quota (Starter plan: 5 requests/month)
const STARTER_PLAN_QUOTA = 5;

test.describe('Billing: Quota Enforcement & Paywall', () => {
  let authToken: string;

  // ============================================================================
  // Setup: Login and get JWT token
  // ============================================================================

  test.beforeAll(async ({ request }) => {
    // Login to get JWT token using OAuth2 password flow (form-urlencoded)
    const loginResponse = await request.post(`${API_BASE_URL}/api/v1/auth/login`, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      data: `username=${encodeURIComponent(TEST_USER.email)}&password=${encodeURIComponent(TEST_USER.password)}`,
    });

    expect(loginResponse.ok()).toBeTruthy();
    const loginData = await loginResponse.json();
    authToken = loginData.access_token;

    expect(authToken).toBeTruthy();
  });

  // ============================================================================
  // Test 1: Successful parser run within quota
  // ============================================================================

  test('should allow parser run within quota limit', async ({ page }) => {
    // Navigate to dashboard
    await page.goto(FRONTEND_URL);

    // Set Zustand store in localStorage (compatible with persist middleware)
    await page.evaluate((token) => {
      const zustandState = {
        state: {
          token: token,
          refreshToken: null,
          user: {
            id: 'test-user-id',
            email: 'test@example.com',
          },
          isAuthenticated: true,
          sidebarCollapsed: false,
          activeNavItem: 'overview',
        },
        version: 0,
      };
      localStorage.setItem('tenable-serm-storage', JSON.stringify(zustandState));
    }, authToken);

    // Reload to apply auth
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Navigate to Reviews page
    await page.click('text=Reviews');
    await expect(page).toHaveURL(/.*reviews/);

    // Open parser form (assuming button exists)
    await page.click('button:has-text("Parse Reviews")');

    // Fill parser form
    await page.fill('input[name="url"]', 'https://2gis.ru/moscow/firm/example');
    await page.selectOption('select[name="platform"]', '2gis');

    // Submit parser job
    await page.click('button:has-text("Start Parsing")');

    // Wait for success toast
    await expect(page.locator('text=Parser job started')).toBeVisible({ timeout: 5000 });
  });

  // ============================================================================
  // Test 2: 6th parser run triggers 402 and shows PaywallModal
  // ============================================================================

  test('should show PaywallModal on quota exceeded (402)', async ({ page, request }) => {
    // Navigate to dashboard
    await page.goto(FRONTEND_URL);

    // Set Zustand store in localStorage
    await page.evaluate((token) => {
      const zustandState = {
        state: {
          token: token,
          refreshToken: null,
          user: { id: 'test-user-id', email: 'test@example.com' },
          isAuthenticated: true,
          sidebarCollapsed: false,
          activeNavItem: 'overview',
        },
        version: 0,
      };
      localStorage.setItem('tenable-serm-storage', JSON.stringify(zustandState));
    }, authToken);

    await page.reload();
    await page.waitForLoadState('networkidle');

    // Mock: Exhaust quota by making 5 successful parser requests
    for (let i = 0; i < STARTER_PLAN_QUOTA; i++) {
      await request.post(`${API_BASE_URL}/api/v1/parser/jobs`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        data: {
          platform: '2gis',
          url: `https://2gis.ru/moscow/firm/test-${i}`,
        },
      });
    }

    // Navigate to Reviews page
    await page.goto(`${FRONTEND_URL}/reviews`);
    await page.waitForLoadState('networkidle');

    // Intercept 6th parser request (should return 402)
    const response402 = page.waitForResponse(
      (response) =>
        response.url().includes('/api/v1/parser/jobs') &&
        response.status() === 402
    );

    // Try to submit 6th parser job (should fail with 402)
    await page.click('button:has-text("Parse Reviews")');
    await page.fill('input[name="url"]', 'https://2gis.ru/moscow/firm/quota-exceeded');
    await page.selectOption('select[name="platform"]', '2gis');
    await page.click('button:has-text("Start Parsing")');

    // Wait for 402 response
    const response = await response402;
    expect(response.status()).toBe(402);

    // PaywallModal should appear automatically
    const paywallModal = page.locator('[data-testid="paywall-modal"]').or(
      page.locator('div:has-text("Upgrade to Pro")')
    );

    await expect(paywallModal).toBeVisible({ timeout: 3000 });

    // Modal should show quota exceeded message
    await expect(page.locator('text=Quota exceeded')).toBeVisible();
    await expect(page.locator('text=5/5 reviews used')).toBeVisible();
  });

  // ============================================================================
  // Test 3: Click "Upgrade to Pro" redirects to Stripe Checkout
  // ============================================================================

  test('should redirect to Stripe Checkout on "Upgrade to Pro" click', async ({ page, context }) => {
    // Navigate to dashboard
    await page.goto(FRONTEND_URL);

    // Set Zustand store in localStorage
    await page.evaluate((token) => {
      const zustandState = {
        state: {
          token: token,
          refreshToken: null,
          user: { id: 'test-user-id', email: 'test@example.com' },
          isAuthenticated: true,
          sidebarCollapsed: false,
          activeNavItem: 'overview',
        },
        version: 0,
      };
      localStorage.setItem('tenable-serm-storage', JSON.stringify(zustandState));
    }, authToken);

    await page.reload();
    await page.waitForLoadState('networkidle');

    // Manually trigger PaywallModal (simulate 402 error)
    await page.evaluate(() => {
      // Dispatch custom event to open PaywallModal
      window.dispatchEvent(new CustomEvent('quota-exceeded', {
        detail: { used: 5, limit: 5 },
      }));
    });

    // Wait for PaywallModal
    const paywallModal = page.locator('[data-testid="paywall-modal"]').or(
      page.locator('button:has-text("Upgrade to Pro")')
    );
    await expect(paywallModal).toBeVisible({ timeout: 3000 });

    // Intercept Stripe Checkout redirect
    const checkoutPromise = page.waitForEvent('popup');

    // Click "Upgrade to Pro"
    await page.click('button:has-text("Upgrade to Pro")');

    // Wait for Stripe Checkout session creation
    const checkoutResponse = await page.waitForResponse(
      (response) =>
        response.url().includes('/api/v1/billing/checkout') &&
        response.status() === 200
    );

    expect(checkoutResponse.ok()).toBeTruthy();

    const checkoutData = await checkoutResponse.json();
    expect(checkoutData.url).toContain('checkout.stripe.com');

    // Verify redirect happened (new tab opens)
    const popup = await checkoutPromise;
    await expect(popup).toHaveURL(/checkout\.stripe\.com/);
  });

  // ============================================================================
  // Test 4: QuotaWidget shows correct usage
  // ============================================================================

  test('should display correct quota usage in QuotaWidget', async ({ page }) => {
    await page.goto(FRONTEND_URL);

    // Set Zustand store in localStorage
    await page.evaluate((token) => {
      const zustandState = {
        state: {
          token: token,
          refreshToken: null,
          user: { id: 'test-user-id', email: 'test@example.com' },
          isAuthenticated: true,
          sidebarCollapsed: false,
          activeNavItem: 'overview',
        },
        version: 0,
      };
      localStorage.setItem('tenable-serm-storage', JSON.stringify(zustandState));
    }, authToken);

    await page.reload();
    await page.waitForLoadState('networkidle');

    // QuotaWidget should be visible in dashboard
    const quotaWidget = page.locator('[data-testid="quota-widget"]').or(
      page.locator('text=5/5 reviews')
    );

    await expect(quotaWidget).toBeVisible({ timeout: 5000 });

    // Verify quota values
    await expect(page.locator('text=5/5')).toBeVisible();
    await expect(page.locator('text=Starter Plan')).toBeVisible();
  });
});

// ============================================================================
// Helper: Reset quota (admin endpoint or database reset)
// ============================================================================

test.afterAll(async ({ request }) => {
  // Optional: Reset quota for test user
  // await request.post(`${API_BASE_URL}/api/v1/admin/reset-quota`, {
  //   headers: { 'Authorization': `Bearer ${authToken}` },
  //   data: { user_id: TEST_USER.email },
  // });
});
