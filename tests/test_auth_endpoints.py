#!/usr/bin/env python3
"""
Тестирование Auth endpoints через requests
"""

from typing import Any

import requests

BASE_URL = "http://localhost:8000"
TEST_EMAIL = "admin@tenable.com"
TEST_PASSWORD = "admin123"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def print_test(name: str, passed: bool, details: str = ""):
    status = (
        f"{Colors.GREEN}✅ PASS{Colors.END}"
        if passed
        else f"{Colors.RED}❌ FAIL{Colors.END}"
    )
    print(f"{status} {name}")
    if details:
        print(f"   {details}")


def test_health():
    """Test 0: Health check"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        passed = response.status_code in [200, 503]
        print_test("Health Check", passed, f"Status: {response.status_code}")
        return passed
    except Exception as e:
        print_test("Health Check", False, str(e))
        return False


def test_register() -> dict[str, Any]:
    """Test 1: Register new user"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )

        # 201 = success, 400 = user exists (both OK for testing)
        passed = response.status_code in [201, 400]

        if response.status_code == 201:
            data = response.json()
            print_test("Register User", passed, f"User ID: {data.get('id')}")
            return {"success": True, "data": data}
        elif response.status_code == 400:
            print_test("Register User", passed, "User already exists (OK)")
            return {"success": True, "exists": True}
        else:
            print_test(
                "Register User", False, f"Unexpected status: {response.status_code}"
            )
            return {"success": False}

    except Exception as e:
        print_test("Register User", False, str(e))
        return {"success": False}


def test_login() -> dict[str, Any]:
    """Test 2: Login with OAuth2 form"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },  # OAuth2 uses 'username'
        )

        passed = response.status_code == 200

        if passed:
            data = response.json()
            access_token = data.get("access_token")
            print_test("Login (OAuth2)", passed, f"Token: {access_token[:20]}...")
            return {"success": True, "access_token": access_token, "data": data}
        else:
            print_test(
                "Login (OAuth2)",
                False,
                f"Status: {response.status_code}, Body: {response.text[:100]}",
            )
            return {"success": False}

    except Exception as e:
        print_test("Login (OAuth2)", False, str(e))
        return {"success": False}


def test_get_me(access_token: str) -> bool:
    """Test 3: Get current user info"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        passed = response.status_code == 200

        if passed:
            data = response.json()
            print_test(
                "Get Current User",
                passed,
                f"Email: {data.get('email')}, Tenant: {data.get('tenant_id', 'N/A')[:8]}...",
            )
        else:
            print_test("Get Current User", False, f"Status: {response.status_code}")

        return passed

    except Exception as e:
        print_test("Get Current User", False, str(e))
        return False


def test_logout(access_token: str) -> bool:
    """Test 4: Logout"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        passed = response.status_code == 200

        if passed:
            data = response.json()
            print_test("Logout", passed, f"Message: {data.get('message')}")
        else:
            print_test("Logout", False, f"Status: {response.status_code}")

        return passed

    except Exception as e:
        print_test("Logout", False, str(e))
        return False


def main():
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}🧪 SERM API Auth Integration Tests{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

    results = []

    # Test 0: Health
    print(f"{Colors.YELLOW}[0/4] Testing Health Endpoint...{Colors.END}")
    results.append(test_health())
    print()

    # Test 1: Register
    print(f"{Colors.YELLOW}[1/4] Testing User Registration...{Colors.END}")
    register_result = test_register()
    results.append(register_result["success"])
    print()

    # Test 2: Login
    print(f"{Colors.YELLOW}[2/4] Testing Login (OAuth2)...{Colors.END}")
    login_result = test_login()
    results.append(login_result["success"])
    print()

    if not login_result["success"]:
        print(f"{Colors.RED}❌ Login failed - skipping remaining tests{Colors.END}\n")
        return

    access_token = login_result["access_token"]

    # Test 3: Get Me
    print(f"{Colors.YELLOW}[3/4] Testing Get Current User...{Colors.END}")
    results.append(test_get_me(access_token))
    print()

    # Test 4: Logout
    print(f"{Colors.YELLOW}[4/4] Testing Logout...{Colors.END}")
    results.append(test_logout(access_token))
    print()

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}📊 Test Results: {passed}/{total} passed{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

    if passed == total:
        print(
            f"{Colors.GREEN}🎉 All tests passed! Auth integration working correctly.{Colors.END}\n"
        )
    else:
        print(
            f"{Colors.RED}⚠️  Some tests failed. Check the output above.{Colors.END}\n"
        )


if __name__ == "__main__":
    main()
