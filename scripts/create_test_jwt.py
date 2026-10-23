#!/usr/bin/env python3
"""Создает валидный JWT токен для тестирования API"""

import json
from uuid import uuid4

import jwt

# Тестовые данные
tenant_id = str(uuid4())
user_id = str(uuid4())
secret = "test-secret-key-for-rls-validation"

# JWT payload
payload = {
    "sub": user_id,
    "tenant_id": tenant_id,
    "aud": "authenticated",
    "exp": 9999999999,  # Далекое будущее
}

# Создаем токен
token = jwt.encode(payload, secret, algorithm="HS256")

print("=== TEST JWT TOKEN ===")
print(f"Token: {token}")
print(f"Tenant ID: {tenant_id}")
print(f"User ID: {user_id}")
print()

# Создаем environment для Postman
env_data = {
    "base_url": "http://localhost:8001",
    "jwt_token": token,
    "tenant_id": tenant_id,
    "user_id": user_id,
}

print("=== POSTMAN ENVIRONMENT ===")
print(json.dumps(env_data, indent=2))
