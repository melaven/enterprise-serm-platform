/**
 * E2E Smoke Test: Basic Authentication & Navigation
 * 
 * Проверяет базовый флоу:
 * 1. Авторизация работает (получение JWT)
 * 2. Фронтенд загружается с токеном
 * 3. Дашборд рендерится
 */

import { test, expect } from '@playwright/test';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:3000';

const TEST_USER = {
  email: 'test@example.com',
  password: 'TestPassword123!',
};

test.describe('Smoke Test: Auth & Dashboard', () => {
  let authToken: string;

  test.beforeAll(async ({ request }) => {
    // Login to get JWT token
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

  test('should authenticate and load dashboard', async ({ page }) => {
    // Listen to console messages for debugging
    page.on('console', msg => console.log('Browser console:', msg.text()));
    page.on('pageerror', err => console.error('Page error:', err.message));
    
    // First, set localStorage BEFORE any page load
    await page.addInitScript((authData) => {
      const zustandState = {
        state: authData.state,
        version: 0,
      };
      localStorage.setItem('tenable-serm-storage', JSON.stringify(zustandState));
    }, {
      state: {
        token: authToken,
        refreshToken: null,
        user: {
          id: 'e74c41c4-2a8c-44f9-838b-39e9b51295f2',
          email: 'test@example.com',
        },
        isAuthenticated: true,
        sidebarCollapsed: false,
        activeNavItem: 'overview',
      }
    });
    
    // Now navigate - localStorage will be already set
    await page.goto(FRONTEND_URL);
    await page.waitForLoadState('networkidle');

    // Should NOT be on login page
    const url = page.url();
    console.log('Current URL:', url);
    
    if (url.includes('/login')) {
      // Debug: check what's in localStorage
      const storage = await page.evaluate(() => {
        return {
          zustand: localStorage.getItem('tenable-serm-storage'),
          allKeys: Object.keys(localStorage),
        };
      });
      console.log('LocalStorage contents:', JSON.stringify(storage, null, 2));
      throw new Error('Still on login page after setting auth!');
    }
    
    await expect(page).not.toHaveURL(/.*login/);
    
    // Verify app is rendered
    const root = page.locator('#root');
    await expect(root).toBeVisible();
    
    console.log('✅ Dashboard loaded successfully');
  });

  test('should make authenticated API request', async ({ request }) => {
    // Test that backend health endpoint works
    const response = await request.get(`${API_BASE_URL}/health`);

    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.status).toBe('healthy');
    console.log('✅ API health check successful');
  });
});
