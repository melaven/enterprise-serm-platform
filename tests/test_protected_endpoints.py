#!/usr/bin/env python3
"""
Тестирование Protected endpoints с Bearer token
"""

import requests

BASE_URL = "http://localhost:8000"
TEST_EMAIL = "admin@tenable.com"
TEST_PASSWORD = "admin123"


def test_quotas_endpoint():
    """Тест GET /api/v1/quotas/status с Bearer token"""

    # 1. Login
    print("1. Логин...")
    login_response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return False

    access_token = login_response.json()["access_token"]
    print(f"✅ Token получен: {access_token[:30]}...")

    # 2. Request to /api/v1/quotas/status
    print("\n2. GET /api/v1/quotas/status...")
    quotas_response = requests.get(
        f"{BASE_URL}/api/v1/quotas/status",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    print(f"Status Code: {quotas_response.status_code}")
    print(f"Response: {quotas_response.text[:200]}")

    if quotas_response.status_code == 200:
        print("✅ Quotas endpoint работает с Bearer token!")
        return True
    else:
        print(f"❌ Quotas endpoint вернул {quotas_response.status_code}")
        return False


if __name__ == "__main__":
    success = test_quotas_endpoint()
    exit(0 if success else 1)
