# Auth Flow & Parser Polling UI

Документация по новым компонентам авторизации и визуализации парсера.

## 📦 Созданные компоненты

### 1. Auth Pages

#### **LoginPage** (`src/pages/LoginPage.tsx`)
- Строгая flat-форма входа на `bg-ink-950`
- Интеграция с `useAppStore.performLogin()` → API `/api/v1/auth/login`
- Сохранение токена и автоматический редирект на `/dashboard`
- Валидация полей и обработка ошибок через `sonner` toasts
- Ссылка на регистрацию

**Стек:**
- TypeScript strict mode (без `any`)
- React Hook Form logic (controlled inputs)
- Tailwind CSS (border-chrome-600, bg-ink-900/950, text-plum)

#### **RegisterPage** (`src/pages/RegisterPage.tsx`)
- Форма регистрации с валидацией пароля (минимум 8 символов)
- Проверка совпадения паролей
- Опциональное поле "Полное имя"
- Интеграция с `useAppStore.performRegister()` → API `/api/v1/auth/register`
- Автоматический редирект после успеха

**Маршруты:**
- `/login` — публичный
- `/register` — публичный
- `/dashboard` — защищенный (через `ProtectedRoute`)

---

### 2. Parser Polling Components

#### **ParserStatusIndicator** (`src/features/parser/ParserStatusIndicator.tsx`)
Визуальный индикатор состояния парсера с анимацией.

**Состояния:**
| State | Badge Variant | Icon | Анимация |
|-------|--------------|------|----------|
| `queued` | secondary | Clock | нет |
| `in_progress` | default (plum) | Loader2 | spin + dots |
| `succeeded` | success (lime) | CheckCircle2 | нет |
| `failed` | destructive | XCircle | нет |

**Props:**
```typescript
interface ParserStatusIndicatorProps {
  state: 'queued' | 'in_progress' | 'succeeded' | 'failed';
  jobId?: string;
  className?: string;
}
```

**Пример использования:**
```tsx
<ParserStatusIndicator 
  state="in_progress" 
  jobId="abc-123-def-456" 
/>
```

#### **useParserPolling** (`src/features/parser/useParserPolling.ts`)
Custom hook для автоматического опроса статуса парсера.

**Логика:**
1. Когда `jobId` существует и статус `queued`/`in_progress`, запускает поллинг каждые 3 сек
2. При `succeeded` → останавливает поллинг, показывает toast, вызывает `onSuccess()`
3. При `failed` → останавливает поллинг, показывает toast с ошибкой
4. Автоматическая очистка интервала при unmount

**API:**
```typescript
interface UseParserPollingOptions {
  onSuccess?: () => void;
  pollInterval?: number; // default: 3000ms
}

const { isPolling, jobId, status, stopPolling } = useParserPolling({
  onSuccess: () => {
    // Обновить данные после парсинга
    fetchReviews({ page_size: 50 });
  }
});
```

**Пример интеграции в ReviewsPage:**
```tsx
const { isPolling, jobId, status } = useParserPolling({
  onSuccess: () => fetchReviews({ page_size: 50 })
});

<ParserStatusIndicator state={status} jobId={jobId} />
<Button disabled={isPolling}>Запустить парсер</Button>
```

---

## 🎨 Дизайн-система

### Цвета (из `tailwind.config.js`)

**Фон:**
- `bg-ink-950` — основной фон страниц auth
- `bg-ink-900` — карточки, формы

**Границы:**
- `border-chrome-600` — input borders (default)
- `border-plum` — focus state

**Текст:**
- `text-white` — заголовки, основной текст
- `text-chrome-300` — labels
- `text-chrome-400` — описания
- `text-chrome-500` — placeholder

**Акценты:**
- `bg-plum`, `text-white` — кнопки по умолчанию
- `text-plum` — ссылки, иконки
- `bg-lime`, `text-black` — success badges

### Компоненты

**Button variants:**
- `default` — plum bg, white text (основной CTA)
- `outline` — transparent bg, chrome border
- `secondary` — chrome-600 bg

**Badge variants:**
- `default` — plum (parser in_progress)
- `secondary` — chrome (parser queued)
- `success` — lime (parser succeeded)
- `destructive` — red (parser failed)

---

## 🔒 Auth Flow

```
1. User → /login (публичный)
   └─ Ввод email/password
   └─ performLogin() → POST /api/v1/auth/login
      ├─ Success → сохранить token в Zustand + localStorage
      │           └─ redirect → /dashboard
      └─ Error → toast с ошибкой

2. User → /register (публичный)
   └─ Ввод email/password/confirmPassword
   └─ Валидация (min 8 chars, passwords match)
   └─ performRegister() → POST /api/v1/auth/register
      ├─ Success → сохранить token + redirect → /dashboard
      └─ Error → toast с ошибкой

3. Protected routes (/dashboard, /reviews, /billing)
   └─ <ProtectedRoute> проверяет isAuthenticated
      ├─ true → рендерит children
      └─ false → redirect → /login
```

---

## 🔄 Parser Polling Flow

```
1. User → ReviewsPage → вводит URL → нажимает "Запустить"
   └─ startParser('2gis', url) → POST /api/v1/parser/start
      └─ Response: { job_id: "abc-123" }
      └─ Zustand: parserJobId = "abc-123", parserStatus = "queued"

2. useParserPolling хук активируется
   └─ Каждые 3 сек: pollParserStatus(jobId) → GET /api/v1/parser/jobs/{id}
      └─ Response: { state: "in_progress", ... }
      └─ Zustand обновляет parserStatus

3. ParserStatusIndicator отображает актуальный state
   ├─ queued → серый бейдж с Clock
   ├─ in_progress → плюм бейдж с анимированным Loader2
   ├─ succeeded → лайм бейдж с CheckCircle2
   │             └─ onSuccess() → fetchReviews()
   └─ failed → красный бейдж с XCircle

4. Поллинг останавливается при succeeded/failed
```

---

## ✅ Checklist

- [x] LoginPage с API интеграцией
- [x] RegisterPage с валидацией
- [x] ParserStatusIndicator с 4 состояниями
- [x] useParserPolling с автоматическим опросом
- [x] Интеграция в ReviewsPage
- [x] Роутинг обновлен (/dashboard добавлен)
- [x] TypeScript strict (без any)
- [x] Pixel-perfect верстка (Ink-950, Chrome-600, Plum, Lime)
- [x] AsyncView обработка loading/error
- [x] Build проходит успешно

---

## 🚀 Запуск

```bash
cd frontend
npm run dev
```

**Тестирование:**
1. Перейти на `http://localhost:5173/login`
2. Ввести email/password → вход
3. Перейти на `/reviews`
4. Ввести URL 2GIS → запустить парсер
5. Наблюдать автоматическое обновление статуса каждые 3 сек
6. При успехе таблица отзывов автоматически обновится

---

**Дизайн-система:** Эталонный B2B-минимализм
**Цвета:** Royal Plum #5A189A, Electric Lime #C5FF4A, Ink-950/900, Chrome-600
**Без теней, градиентов, blur** (corePlugins disabled)
