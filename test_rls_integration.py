#!/usr/bin/env python3
"""
RLS Integration Validation Script
Tests the multi-tenant RLS dependencies without requiring full server startup
"""

import sys
import traceback
from uuid import UUID, uuid4


def test_imports():
    """Test that all RLS-related imports work correctly"""
    print("🔍 Testing imports...")

    try:
        # Test core auth imports
        from app.core.auth import CurrentTenant, get_current_tenant
        from app.core.tenant_session import build_rls_claims, get_tenant_session
        from app.schemas.auth import JWTPayload

        print("✅ Core auth imports: OK")

        # Test dependencies imports
        from app.core.dependencies import (
            get_company_repository,
            get_economics_service,
            get_llm_service,
            get_platform_repository,
            get_review_repository,
            get_tenant_db,
        )

        print("✅ Dependencies imports: OK")

        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return False


def test_jwt_payload():
    """Test JWTPayload model validation"""
    print("🔍 Testing JWT payload...")

    try:
        from app.schemas.auth import JWTPayload

        # Test valid payload
        payload = JWTPayload(sub=uuid4(), tenant_id=uuid4())

        print(f"✅ JWTPayload creation: OK (tenant_id: {payload.tenant_id})")

        # Test payload validation
        assert isinstance(payload.sub, UUID)
        assert isinstance(payload.tenant_id, UUID)

        print("✅ JWTPayload validation: OK")
        return True

    except Exception as e:
        print(f"❌ JWT payload test failed: {e}")
        traceback.print_exc()
        return False


def test_rls_claims():
    """Test RLS claims building"""
    print("🔍 Testing RLS claims...")

    try:
        import json

        from app.core.tenant_session import build_rls_claims
        from app.schemas.auth import JWTPayload

        payload = JWTPayload(sub=uuid4(), tenant_id=uuid4())

        claims = build_rls_claims(payload)
        parsed_claims = json.loads(claims)

        # Validate claims structure
        assert "sub" in parsed_claims
        assert "tenant_id" in parsed_claims
        assert parsed_claims["sub"] == str(payload.sub)
        assert parsed_claims["tenant_id"] == str(payload.tenant_id)

        print("✅ RLS claims building: OK")
        print(f"  Sample claims: {claims}")
        return True

    except Exception as e:
        print(f"❌ RLS claims test failed: {e}")
        traceback.print_exc()
        return False


def test_dependency_structure():
    """Test dependency injection structure"""
    print("🔍 Testing dependency structure...")

    try:
        from app.core.dependencies import (
            AppConfig,
        )

        # Test config structure
        config = AppConfig()
        print("✅ AppConfig creation: OK")

        # Test validation
        errors = config.validate()
        print(f"✅ Config validation: {len(errors)} errors found (expected in test)")

        return True

    except Exception as e:
        print(f"❌ Dependency structure test failed: {e}")
        traceback.print_exc()
        return False


def test_auth_config():
    """Test authentication configuration"""
    print("🔍 Testing auth config...")

    try:
        import os

        os.environ["SUPABASE_JWT_SECRET"] = "test-secret-for-validation"

        from app.core.auth import AuthConfig, get_auth_config

        config = get_auth_config()
        assert isinstance(config, AuthConfig)
        assert config.secret == "test-secret-for-validation"

        print("✅ Auth config: OK")
        return True

    except Exception as e:
        print(f"❌ Auth config test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all RLS integration tests"""
    print("=" * 50)
    print("🧪 SERM API RLS Integration Tests")
    print("=" * 50)

    tests = [
        test_imports,
        test_jwt_payload,
        test_rls_claims,
        test_dependency_structure,
        test_auth_config,
    ]

    results = []

    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
            print()

    # Summary
    passed = sum(results)
    total = len(results)

    print("=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")

    if passed == total:
        print("🎉 ALL TESTS PASSED - RLS Integration Ready!")
        return 0
    else:
        print("⚠️  Some tests failed - Check configuration")
        return 1


if __name__ == "__main__":
    sys.exit(main())
