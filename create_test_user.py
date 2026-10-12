"""
Создание тестового пользователя для Dashboard API
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("СОЗДАНИЕ ТЕСТОВОГО ПОЛЬЗОВАТЕЛЯ")
print("=" * 60)

# Данные нового пользователя
user_data = {
    "email": "test@example.com",
    "password": "TestPassword123!",
    "tenant_id": "11111111-1111-1111-1111-111111111111"
}

try:
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json=user_data
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code in [200, 201]:
        print("\n✅ Пользователь создан успешно!")
        print(f"   Email: {user_data['email']}")
        print(f"   Password: {user_data['password']}")
        print(f"   Tenant ID: {user_data['tenant_id']}")
    elif response.status_code == 400:
        print("\n⚠️ Пользователь уже существует")
        print(f"   Можно использовать для логина:")
        print(f"   Email: {user_data['email']}")
        print(f"   Password: {user_data['password']}")
    else:
        print(f"\n❌ Ошибка создания пользователя")
        
except Exception as e:
    print(f"❌ Ошибка соединения: {str(e)}")

print("\n" + "=" * 60)
print("Попытка логина...")
print("=" * 60)

# Пробуем залогиниться
login_data = {
    "username": user_data["email"],
    "password": user_data["password"]
}

try:
    login_response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"Status Code: {login_response.status_code}")
    
    if login_response.status_code == 200:
        login_result = login_response.json()
        access_token = login_result.get("access_token")
        print(f"\n✅ Логин успешен!")
        print(f"   Token: {access_token[:50]}...")
    else:
        print(f"\n❌ Ошибка логина")
        print(f"   Response: {json.dumps(login_response.json(), indent=2)}")
        
except Exception as e:
    print(f"❌ Ошибка: {str(e)}")
