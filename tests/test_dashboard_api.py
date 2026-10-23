"""
Тестирование Dashboard API эндпоинтов
GET /api/v1/reviews - список отзывов с пагинацией
GET /api/v1/reviews/summary - KPI-метрики
"""

import json

import requests

BASE_URL = "http://localhost:8000"

# Шаг 1: Логин для получения JWT токена
print("=" * 60)
print("1. АВТОРИЗАЦИЯ")
print("=" * 60)

# OAuth2PasswordRequestForm использует username, а не email
login_data = {"username": "test@example.com", "password": "TestPassword123!"}

try:
    login_response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data=login_data,  # OAuth2 использует form data, не JSON
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code == 200:
        login_result = login_response.json()
        access_token = login_result.get("access_token")
        print("✅ Логин успешен")
        print(f"   Access Token: {access_token[:50]}...")
        print(f"   Token Type: {login_result.get('token_type')}")
    else:
        print(f"❌ Ошибка логина: {login_response.status_code}")
        print(f"   Response: {login_response.text}")
        exit(1)

except Exception as e:
    print(f"❌ Ошибка соединения: {str(e)}")
    exit(1)

# Заголовки авторизации
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

# Шаг 2: Тест GET /api/v1/reviews (список с пагинацией)
print("\n" + "=" * 60)
print("2. GET /api/v1/reviews - Список отзывов")
print("=" * 60)

try:
    reviews_response = requests.get(
        f"{BASE_URL}/api/v1/reviews",
        headers=headers,
        params={
            "page": 1,
            "page_size": 10,
            "sort_by": "created_at",
            "sort_order": "desc",
        },
    )

    print(f"Status Code: {reviews_response.status_code}")

    if reviews_response.status_code == 200:
        reviews_data = reviews_response.json()

        if reviews_data.get("success"):
            data = reviews_data.get("data", {})
            items = data.get("items", [])

            print("✅ Список отзывов получен")
            print(f"   Всего отзывов: {data.get('total')}")
            print(f"   Страница: {data.get('page')}/{data.get('total_pages')}")
            print(f"   На странице: {len(items)}")

            if items:
                print("\n   Первый отзыв:")
                first = items[0]
                print(f"   - ID: {first.get('id')}")
                print(f"   - Platform: {first.get('platform')}")
                print(f"   - Rating: {first.get('rating')}")
                print(f"   - Author: {first.get('author_name')}")
                print(f"   - Sentiment: {first.get('sentiment')}")
                print(f"   - Text: {first.get('text', '')[:100]}...")
        else:
            print("❌ Запрос неуспешен")
            print(f"   Response: {json.dumps(reviews_data, indent=2)}")
    else:
        print(f"❌ Ошибка: {reviews_response.status_code}")
        print(f"   Response: {reviews_response.text}")

except Exception as e:
    print(f"❌ Ошибка запроса: {str(e)}")

# Шаг 3: Тест GET /api/v1/reviews/summary (KPI-метрики)
print("\n" + "=" * 60)
print("3. GET /api/v1/reviews/summary - KPI Метрики")
print("=" * 60)

try:
    summary_response = requests.get(
        f"{BASE_URL}/api/v1/reviews/summary", headers=headers, params={"days": 30}
    )

    print(f"Status Code: {summary_response.status_code}")

    if summary_response.status_code == 200:
        summary_data = summary_response.json()

        if summary_data.get("success"):
            data = summary_data.get("data", {})

            print("✅ KPI-метрики получены")
            print("\n   📊 Основные метрики:")
            print(f"   - Всего отзывов: {data.get('total_reviews')}")
            print(f"   - За период (30 дней): {data.get('total_reviews_period')}")
            print(f"   - Средний рейтинг: {data.get('average_rating')}/5.0")
            print(f"   - Критичные отзывы: {data.get('critical_count')}")
            print(f"   - Требуют ответа: {data.get('pending_response')}")
            print(f"   - Финансовое влияние: {data.get('total_financial_impact')}")

            print("\n   😊 Тональность:")
            sentiment = data.get("sentiment_distribution", {})
            print(f"   - Positive: {sentiment.get('positive', 0)}")
            print(f"   - Neutral: {sentiment.get('neutral', 0)}")
            print(f"   - Negative: {sentiment.get('negative', 0)}")

            print("\n   ⭐ Распределение рейтингов:")
            ratings = data.get("rating_distribution", {})
            for star in ["5", "4", "3", "2", "1"]:
                count = ratings.get(star, 0)
                print(f"   - {star} звёзд: {count}")
        else:
            print("❌ Запрос неуспешен")
            print(f"   Response: {json.dumps(summary_data, indent=2)}")
    else:
        print(f"❌ Ошибка: {summary_response.status_code}")
        print(f"   Response: {summary_response.text}")

except Exception as e:
    print(f"❌ Ошибка запроса: {str(e)}")

# Шаг 4: Тест фильтрации и сортировки
print("\n" + "=" * 60)
print("4. Тест фильтрации (rating=5, platform=google)")
print("=" * 60)

try:
    filtered_response = requests.get(
        f"{BASE_URL}/api/v1/reviews",
        headers=headers,
        params={
            "page": 1,
            "page_size": 5,
            "rating": 5,
            "platform": "google",
            "sort_by": "rating",
            "sort_order": "desc",
        },
    )

    print(f"Status Code: {filtered_response.status_code}")

    if filtered_response.status_code == 200:
        filtered_data = filtered_response.json()

        if filtered_data.get("success"):
            data = filtered_data.get("data", {})
            items = data.get("items", [])

            print("✅ Фильтрация работает")
            print(f"   Найдено: {data.get('total')} отзывов")
            print(f"   На странице: {len(items)}")

            if items:
                for idx, review in enumerate(items, 1):
                    print(
                        f"\n   {idx}. Rating: {review.get('rating')}, Platform: {review.get('platform')}"
                    )
        else:
            print("❌ Запрос неуспешен")
            print(f"   Response: {json.dumps(filtered_data, indent=2)}")
    else:
        print(f"❌ Ошибка: {filtered_response.status_code}")
        print(f"   Response: {filtered_response.text}")

except Exception as e:
    print(f"❌ Ошибка запроса: {str(e)}")

print("\n" + "=" * 60)
print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 60)
