#!/usr/bin/env python3
"""
Тестирование Parser API с JWT защитой
Проверка: аутентификация, RLS изоляция, квотные лимиты
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

class ParserAPISecurityTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.jwt_token = None
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_health_check(self) -> Dict[str, Any]:
        """Проверка работоспособности API"""
        print("🔍 Testing API health...")
        try:
            async with self.session.get(f"{self.base_url}/health") as resp:
                return {
                    "status": "✅ PASS" if resp.status in [200, 503] else "❌ FAIL",
                    "status_code": resp.status,
                    "data": await resp.json()
                }
        except Exception as e:
            return {"status": "❌ FAIL", "error": str(e)}
    
    async def test_auth_login(self) -> Dict[str, Any]:
        """Аутентификация для получения JWT токена"""
        print("🔐 Testing authentication...")
        try:
            login_data = {
                "username": "test@example.com",
                "password": "TestPassword123!"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                data=login_data
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.jwt_token = data.get("access_token")
                    return {
                        "status": "✅ PASS",
                        "status_code": resp.status,
                        "token_received": bool(self.jwt_token),
                        "token_type": data.get("token_type")
                    }
                else:
                    return {
                        "status": "❌ FAIL",
                        "status_code": resp.status,
                        "data": await resp.json()
                    }
        except Exception as e:
            return {"status": "❌ FAIL", "error": str(e)}
    
    async def test_parser_unauthorized(self) -> Dict[str, Any]:
        """Тест доступа к Parser API без токена (должен блокироваться)"""
        print("🚫 Testing unauthorized access (should be blocked)...")
        try:
            test_data = {
                "url": "https://maps.google.com/test-location"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/parsers/start",
                json=test_data
            ) as resp:
                return {
                    "status": "✅ PASS" if resp.status == 401 else "❌ FAIL",
                    "status_code": resp.status,
                    "expected": "401 Unauthorized",
                    "data": await resp.json() if resp.status != 401 else {"message": "Correctly blocked"}
                }
        except Exception as e:
            return {"status": "❌ FAIL", "error": str(e)}
    
    async def test_parser_authorized(self) -> Dict[str, Any]:
        """Тест доступа к Parser API с валидным JWT токеном"""
        print("✅ Testing authorized access...")
        if not self.jwt_token:
            return {"status": "❌ SKIP", "reason": "No JWT token available"}
        
        try:
            test_data = {
                "url": "https://maps.google.com/test-location"
            }
            
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
            
            async with self.session.post(
                f"{self.base_url}/api/v1/parsers/start",
                json=test_data,
                headers=headers
            ) as resp:
                return {
                    "status": "✅ PASS" if resp.status in [200, 402] else "❌ FAIL",
                    "status_code": resp.status,
                    "expected": "200 OK or 402 Payment Required (quota)",
                    "data": await resp.json()
                }
        except Exception as e:
            return {"status": "❌ FAIL", "error": str(e)}
    
    async def test_queue_stats_security(self) -> Dict[str, Any]:
        """Тест доступа к статистике очереди с JWT защитой"""
        print("📊 Testing queue stats security...")
        if not self.jwt_token:
            return {"status": "❌ SKIP", "reason": "No JWT token available"}
        
        try:
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
            
            async with self.session.get(
                f"{self.base_url}/api/v1/parsers/queue/stats",
                headers=headers
            ) as resp:
                data = await resp.json()
                return {
                    "status": "✅ PASS" if resp.status == 200 else "❌ FAIL",
                    "status_code": resp.status,
                    "tenant_isolated": "tenant_id" in data,
                    "security_verified": data.get("security", {}).get("authenticated", False),
                    "data": data
                }
        except Exception as e:
            return {"status": "❌ FAIL", "error": str(e)}
    
    async def test_invalid_jwt(self) -> Dict[str, Any]:
        """Тест с недействительным JWT токеном"""
        print("🔒 Testing invalid JWT token...")
        try:
            test_data = {
                "url": "https://maps.google.com/test-location"
            }
            
            headers = {"Authorization": "Bearer invalid-token-123"}
            
            async with self.session.post(
                f"{self.base_url}/api/v1/parsers/start",
                json=test_data,
                headers=headers
            ) as resp:
                return {
                    "status": "✅ PASS" if resp.status == 401 else "❌ FAIL",
                    "status_code": resp.status,
                    "expected": "401 Unauthorized",
                    "data": await resp.json()
                }
        except Exception as e:
            return {"status": "❌ FAIL", "error": str(e)}


async def run_security_tests():
    """Запуск всех тестов безопасности"""
    print("🛡️ SERM Parser API Security Tests")
    print("=" * 50)
    
    async with ParserAPISecurityTester() as tester:
        tests = [
            ("Health Check", tester.test_health_check),
            ("Authentication", tester.test_auth_login),
            ("Unauthorized Access Block", tester.test_parser_unauthorized),
            ("Invalid JWT Block", tester.test_invalid_jwt),
            ("Authorized Access", tester.test_parser_authorized),
            ("Queue Stats Security", tester.test_queue_stats_security),
        ]
        
        results = {}
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}:")
            result = await test_func()
            results[test_name] = result
            
            if result["status"] == "✅ PASS":
                passed += 1
                print(f"   {result['status']} Status: {result.get('status_code', 'N/A')}")
            elif result["status"] == "❌ FAIL":
                print(f"   {result['status']} Error: {result.get('error', result.get('data', 'Unknown'))}")
            else:
                print(f"   {result['status']} {result.get('reason', '')}")
        
        # Сводка
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY:")
        print(f"   Passed: {passed}/{total}")
        print(f"   Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("   🎉 ALL SECURITY TESTS PASSED!")
        else:
            print("   ⚠️  Some tests failed - check security implementation")
        
        return results


if __name__ == "__main__":
    asyncio.run(run_security_tests())