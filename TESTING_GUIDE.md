# 🧪 Tenable SERM - Testing Guide

## 🚀 Quick Start (для тестирования)

### 1. Backend
```bash
# В терминале 1
cd "c:\Users\Malyarenko17\Desktop\ОСНОВНЫЕ ПРОЕКТЫ\Tenable SERM"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Или просто:
start_backend.bat
```

### 2. ARQ Worker (опционально)
```bash
# В терминале 2
cd "c:\Users\Malyarenko17\Desktop\ОСНОВНЫЕ ПРОЕКТЫ\Tenable SERM"
python worker.py

# Или:
start_worker.bat
```

### 3. Frontend
```bash
# В терминале 3
cd "c:\Users\Malyarenko17\Desktop\ОСНОВНЫЕ ПРОЕКТЫ\Tenable SERM\frontend"
npm run dev

# Или:
start_frontend.bat
```

---

## 📝 Создание тестового пользователя

Если пользователя ещё нет, создайте через Swagger UI или curl:

### Через Swagger UI (рекомендуется):
1. Откройте `http://localhost:8000/docs`
2. Найдите endpoint `POST /api/v1/auth/register`
3. Нажмите "Try it out"
4. Введите:
```json
{
  "email": "admin@tenable.com",
  "password": "admin123",
  "tenant_id": "tenant-001"
}
```
5. Execute

### Через curl:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@tenable.com",
    "password": "admin123",
    "tenant_id": "tenant-001"
  }'
```

---

## 🔍 Тестовый сценарий

### Шаг 1: Откройте приложение
```
http://localhost:3000
```

**Ожидание:** Редирект на `/login`

---

### Шаг 2: Авторизация
**Данные:**
- Email: `admin@tenable.com`
- Password: `admin123`

**Ожидание:**
- Toast: "Успешный вход!"
- Редирект на `/` (Dashboard)
- Email в sidebar снизу
- QuotaWidget показывает квоты

---

### Шаг 3: Проверка данных

**AnalysisPanel (сверху):**
- Всего отзывов: 0 (если база пустая)
- Средний рейтинг: 0.0 ★
- Тренд: →
- Статус: Активен (зелёный badge)

**ReviewsTable (снизу):**
- Если нет отзывов → Empty State:
  ```
  📋
  Нет отзывов
  Отзывы появятся здесь после запуска сбора данных
  ```

**QuotaWidget (sidebar, внизу):**
- LLM Токены: X / 100,000
- Парсинг: X / 5,000
- Прогресс-бары (Lime цвет)

---

### Шаг 4: Запуск сбора (ГЛАВНЫЙ ТЕСТ!)

**Действие:** Нажмите кнопку **"▶ Запустить сбор"** (фиолетовая, в AnalysisPanel)

**Что происходит:**
1. Кнопка становится "Запуск..." (disabled)
2. POST запрос на `/api/v1/parsers/start`

**Возможные результаты:**

#### ✅ Успех (200-202):
```
Toast (зелёный):
"Сбор отзывов запущен!"
"Отзывы будут обработаны в фоновом режиме"
```

#### ⚠️ Лимит исчерпан (402):
```
Toast (красный):
"Ошибка биллинга: Лимит токенов или запросов исчерпан"
"Пожалуйста, обновите тарифный план или дождитесь следующего периода"
```

#### 🔴 Другие ошибки:
- 401 → Редирект на /login
- 429 → "Слишком много запросов"
- 500 → "Не удалось запустить сбор отзывов"

---

### Шаг 5: Мониторинг

**В DevTools → Network:**
- Смотрите POST `/api/v1/parsers/start`
- Статус код: 202, 402, или другой
- Response body с деталями

**В Backend логах:**
```
INFO: POST /api/v1/parsers/start
INFO: Quota check passed
INFO: Job enqueued: parse_reviews
```

**В ARQ Worker логах (если запущен):**
```
INFO: Job parse_reviews started
INFO: Parsing reviews for tenant: tenant-001
INFO: Job completed in 5.2s
```

---

### Шаг 6: Проверка обновления

**Подождите 5-10 секунд и нажмите "Обновить"** в ReviewsTable.

**Ожидание:**
- Skeleton Loader (серые полоски)
- Загрузка данных
- Появление отзывов в таблице (если парсер нашёл данные)
- Обновление QuotaWidget (использование токенов увеличилось)

---

## 🎨 UI/UX проверки

### Flat-Design:
- [ ] Нет теней (shadow) нигде
- [ ] Нет градиентов
- [ ] Нет blur эффектов
- [ ] Максимум 2px скругления

### Цвета:
- [ ] Фон: Ink (#0B0B0F)
- [ ] Текст: Chrome (#C9CED6)
- [ ] Primary кнопки: Plum (#5A189A)
- [ ] Акценты: Lime (#C5FF4A)

### Компоненты:
- [ ] shadcn/ui Button работает
- [ ] shadcn/ui Badge цвета корректные
- [ ] shadcn/ui Table отображается правильно
- [ ] Skeleton loader показывается при загрузке
- [ ] Empty State показывается когда нет данных
- [ ] Toast notifications появляются

---

## 🐛 Что проверять при багах

### Авторизация не работает:
1. Backend запущен? (`http://localhost:8000/docs`)
2. Пользователь создан? (проверь через Swagger)
3. Токен сохраняется? (`localStorage.getItem('auth_token')`)
4. CORS настроен? (проверь в backend логах)

### Данные не загружаются:
1. Authorization header есть? (DevTools → Network)
2. Backend отдаёт данные? (Swagger UI → Try endpoint)
3. tenant_id совпадает? (check JWT payload)

### Парсер не запускается:
1. Redis работает? (`redis-cli ping`)
2. ARQ Worker запущен?
3. Квоты не исчерпаны? (проверь в БД)

### Toast не показываются:
1. Sonner установлен? (`npm list sonner`)
2. Toaster добавлен в main.tsx?
3. Импорт правильный? (`from 'sonner'`)

---

## 📊 Ожидаемые метрики

### Без данных (первый запуск):
```
Всего отзывов: 0
Средний рейтинг: 0.0 ★
LLM Токены: 0 / 100,000 (0.0%)
Парсинг: 0 / 5,000 (0.0%)
```

### После запуска парсера (успех):
```
Всего отзывов: 5-50 (зависит от источника)
Средний рейтинг: 3.5-4.5 ★
LLM Токены: 2000-5000 / 100,000 (2-5%)
Парсинг: 1 / 5,000 (0.02%)
```

### При исчерпании лимита:
```
POST /api/v1/parsers/start → 402
Toast: "Ошибка биллинга..."
QuotaWidget: красный/желтый прогресс-бар
```

---

## ✅ Финальный Checklist

### Перед началом:
- [ ] PostgreSQL доступен (Supabase)
- [ ] Redis запущен (optional для worker)
- [ ] Python dependencies установлены
- [ ] npm dependencies установлены

### Backend:
- [ ] Сервер запустился (port 8000)
- [ ] Swagger UI открывается
- [ ] Healthcheck работает (`/health`)
- [ ] Database подключена

### Frontend:
- [ ] Dev сервер запустился (port 3000)
- [ ] Нет ошибок компиляции
- [ ] Hot reload работает

### Full Flow:
- [ ] Login работает
- [ ] Protected routes работают
- [ ] API requests с токеном
- [ ] ReviewsTable загружает данные
- [ ] AnalysisPanel показывает метрики
- [ ] QuotaWidget обновляется
- [ ] "Запустить сбор" работает
- [ ] Toast notifications показываются
- [ ] 402 error перехватывается

---

## 🎯 Успех!

Если все пункты выполнены — **поздравляю!** 

У вас работает полноценная интеграция:
- ✅ Frontend ↔ Backend
- ✅ JWT авторизация
- ✅ Protected routes
- ✅ Real-time квоты
- ✅ Billing error handling
- ✅ Professional UI/UX

**Можно двигаться дальше! 🚀**
