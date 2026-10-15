# Frontend Architecture — Tenable SERM

## 📁 Структура директорий

```
frontend/src/
├── api/                          # API Layer (centralized)
│   ├── client.ts                 # Axios базовый клиент с interceptors
│   ├── errorHandler.ts           # Централизованная обработка ошибок
│   ├── services.ts               # API endpoints (reviews, parser, auth)
│   ├── quota.ts                  # Quota state management
│   └── index.ts                  # Barrel export для API
│
├── components/                   # Shared UI Components
│   ├── glass/                    # Glassmorphism Components
│   │   ├── glass-card.tsx        # GlassCard, GlassCardHeader, GlassCardContent
│   │   ├── glass-progress.tsx   # GlassProgress, GlassCircularProgress
│   │   └── index.ts              # Barrel export
│   │
│   └── ui/                       # Base shadcn/ui Components
│       ├── badge.tsx             # Badge (sentiment, status)
│       ├── button.tsx            # Button (primary, secondary, ghost)
│       ├── skeleton.tsx          # Skeleton loader
│       ├── sonner.tsx            # Toast notifications
│       └── table.tsx             # Table primitives
│
├── features/                     # Feature Modules (business logic)
│   ├── auth/                     # Authentication Feature
│   │   ├── AuthShell.tsx         # Layout для login/register
│   │   ├── ProtectedRoute.tsx   # Route guard с редиректом
│   │   └── index.ts              # Barrel export
│   │
│   ├── dashboard/                # Dashboard Feature
│   │   ├── DashboardLayout.tsx   # Sidebar + header layout
│   │   ├── QuotaWidget.tsx       # Compact quota display
│   │   ├── QuotaModal.tsx        # Full-screen quota modal
│   │   ├── QuotaExceededDialog.tsx  # 402 Paywall dialog
│   │   ├── QuotaExceededHost.tsx    # Global quota listener
│   │   └── index.ts              # Barrel export
│   │
│   └── reviews/                  # Reviews Feature
│       ├── ReviewsTable.tsx      # Reviews table с pagination
│       ├── AnalysisPanel.tsx     # Analytics dashboard
│       └── index.ts              # Barrel export
│
├── pages/                        # Route Pages
│   ├── BillingPage.tsx           # /billing — тарифы и оплата
│   ├── LoginPage.tsx             # /login — авторизация
│   ├── RegisterPage.tsx          # /register — регистрация
│   └── ReviewsPage.tsx           # /reviews — управление отзывами
│
├── store/                        # State Management (Zustand)
│   └── useAppStore.ts            # Unified store (auth, reviews, parser)
│
├── lib/                          # Utilities
│   └── utils.ts                  # cn() helper для Tailwind
│
├── App.tsx                       # Root component (устарел, используйте ReviewsPage)
├── main.tsx                      # Entry point + routing
├── index.css                     # Global styles + Tailwind base
└── vite-env.d.ts                 # TypeScript definitions

```

---

## 🎨 Design System

### Цветовая палитра

| Токен          | HEX       | Использование                                 |
|----------------|-----------|-----------------------------------------------|
| **Ink**        | `#000000` | Фон приложения (`bg-black`)                   |
| **Chrome**     | `zinc-*`  | Рамки (`zinc-800`), второстепенный текст      |
| **Royal Plum** | `#5A189A` | Кнопки (`bg-plum`), активные элементы         |
| **Plum Deep**  | `#43127A` | Hover состояния (`bg-plum-deep`)             |
| **Electric Lime** | `#C5FF4A` | Позитивные метрики, успех, прогресс (`bg-lime`) |
| **Crimson**    | `#A4172A` | Ошибки, критичные зоны (`bg-crimson`)         |

### Glassmorphism Specs

- **Фон**: `bg-white/5` (5% white overlay)
- **Размытие**: `backdrop-blur-2xl` (глубокое размытие)
- **Рамки**: `border border-white/10` (тонкие полупрозрачные)
- **Тени**: Многослойные (3-4 слоя):
  ```css
  shadow-[0_4px_12px_rgba(0,0,0,0.4),0_8px_32px_rgba(0,0,0,0.3),0_16px_48px_rgba(0,0,0,0.2)]
  ```
- **Радиусы**: `rounded-sm` (2px везде, включая карточки и кнопки)
- **Запрещено**: градиенты, неон, box-shadow на элементах (кроме Glass)

---

## 🔧 Технологический стек

| Категория         | Технология              | Назначение                          |
|-------------------|-------------------------|-------------------------------------|
| **Framework**     | React 18 + TypeScript   | UI framework                        |
| **Bundler**       | Vite                    | Build tool + dev server             |
| **Styling**       | Tailwind CSS v3         | Utility-first CSS                   |
| **UI Library**    | shadcn/ui               | Headless primitives (button, table) |
| **State**         | Zustand + persist       | Lightweight state management        |
| **Routing**       | React Router v6         | SPA routing                         |
| **API Client**    | Axios                   | HTTP requests + interceptors        |
| **Notifications** | Sonner                  | Toast notifications                 |
| **Icons**         | Lucide React            | Icon library                        |
| **Fonts**         | @fontsource (Inter, JetBrains Mono) | Self-hosted fonts     |

---

## 🚀 Импорты и алиасы

### Path Alias Configuration

В `tsconfig.json` и `vite.config.ts` настроен alias `@/`:

```json
{
  "baseUrl": ".",
  "paths": {
    "@/*": ["./src/*"]
  }
}
```

### Правила импортов

#### ✅ **Используйте alias для src/**
```tsx
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store/useAppStore';
import { ReviewsTable } from '@/features/reviews';
```

#### ✅ **Barrel exports для features/**
```tsx
// Вместо:
import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { QuotaWidget } from '@/features/dashboard/QuotaWidget';

// Используйте:
import { DashboardLayout, QuotaWidget } from '@/features/dashboard';
```

#### ✅ **Относительные импорты внутри одной feature**
```tsx
// Внутри features/dashboard/
import { QuotaWidget } from './QuotaWidget';
```

#### ❌ **НЕ используйте**
```tsx
// Относительные импорты через родительские директории
import { Button } from '../../../components/ui/button';

// Импорт из другой feature напрямую (только через barrel)
import { ReviewsTable } from '@/features/reviews/ReviewsTable';
```

---

## 📦 State Management (Zustand)

### Структура Store

```tsx
interface AppStore {
  // Auth
  user: User | null;
  token: string | null;
  login: (email, password) => Promise<void>;
  register: (email, password) => Promise<void>;
  logout: () => void;
  
  // Reviews
  reviews: Review[];
  loadReviews: () => Promise<void>;
  
  // Parser
  parserStatus: 'idle' | 'running' | 'completed';
  startParser: (url, platform) => Promise<void>;
  
  // Analytics
  analytics: AnalyticsSummary | null;
  loadAnalytics: () => Promise<void>;
}
```

### Использование

```tsx
// Подписка на конкретные части store
const { user, login } = useAppStore(state => ({
  user: state.user,
  login: state.login
}));

// Доступ к функциям
const { startParser } = useParser();
const { reviews, loadReviews } = useReviews();
```

---

## 🧩 Feature Modules

### Принципы организации

1. **Инкапсуляция**: Каждая feature содержит свою UI логику
2. **Barrel Exports**: Внешний мир видит только публичный API через `index.ts`
3. **Минимальные зависимости**: Features не импортируют друг друга напрямую
4. **Shared components**: Общие компоненты в `components/ui/` и `components/glass/`

### Пример: Reviews Feature

```
features/reviews/
├── ReviewsTable.tsx       # Главный компонент
├── AnalysisPanel.tsx      # Аналитика
└── index.ts               # export { ReviewsTable, AnalysisPanel }
```

Использование:
```tsx
import { ReviewsTable, AnalysisPanel } from '@/features/reviews';
```

---

## 🎯 API Layer

### Централизованный клиент

```tsx
// api/client.ts
export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});

// Interceptors для JWT и error handling
apiClient.interceptors.request.use(addAuthHeader);
apiClient.interceptors.response.use(null, handleApiError);
```

### Сервисы

```tsx
// api/services.ts
export const reviewsApi = {
  list: (params) => apiClient.get('/reviews', { params }),
  getById: (id) => apiClient.get(`/reviews/${id}`),
};

export const parserApi = {
  start: (url, platform) => apiClient.post('/parser/start', { url, platform }),
  status: (jobId) => apiClient.get(`/parser/${jobId}/status`),
};
```

### Error Handling

```tsx
// api/errorHandler.ts
export function withErrorHandling<T>(
  fn: () => Promise<T>,
  fallback?: T
): Promise<T> {
  return fn().catch(error => {
    toast.error(error.message);
    return fallback ?? Promise.reject(error);
  });
}
```

---

## 🧪 Типы и TypeScript

### Конвенции именования

```tsx
// ✅ Интерфейсы с префиксом I (опционально)
interface Review { ... }
interface IReviewProps { ... }

// ✅ Type aliases для unions
type Sentiment = 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
type Platform = '2gis' | 'yandex' | 'google' | 'trustpilot';

// ✅ Props с суффиксом Props
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
}
```

### API Response Types

```tsx
// Синхронизированы с backend (FastAPI Pydantic models)
export interface Review {
  id: string;
  platform: Platform;
  author: string | null;
  rating: number;
  text: string;
  sentiment: Sentiment;
  ai_tags: string[];
  ai_reply_draft: string | null;
  created_at: string;
}
```

---

## 🚦 Routing Strategy

### Структура маршрутов

```tsx
// main.tsx
<Routes>
  {/* Public Routes */}
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
  
  {/* Protected Routes */}
  <Route element={<ProtectedRoute />}>
    <Route path="/reviews" element={<ReviewsPage />} />
    <Route path="/billing" element={<BillingPage />} />
  </Route>
  
  {/* Fallback */}
  <Route path="/" element={<Navigate to="/reviews" replace />} />
</Routes>
```

### Protected Route Guard

```tsx
export const ProtectedRoute = () => {
  const { token } = useAuth();
  return token ? <Outlet /> : <Navigate to="/login" replace />;
};
```

---

## 🎨 Styling Best Practices

### Tailwind Conventions

```tsx
// ✅ Используйте утилиты первого порядка
<div className="flex items-center gap-4 rounded-sm border border-white/10 bg-white/5 p-6 backdrop-blur-2xl">

// ✅ Группируйте классы по категориям
<div className={cn(
  // Layout
  'flex items-center justify-between',
  // Spacing
  'gap-4 p-6',
  // Styling
  'rounded-sm border border-white/10 bg-white/5 backdrop-blur-2xl',
  // Responsive
  'sm:flex-row sm:gap-6',
  // Conditional
  isActive && 'border-lime bg-lime/10'
)}>

// ❌ НЕ создавайте произвольные CSS классы
<div className="my-custom-card"> {/* избегайте */}
```

### cn() Helper

```tsx
import { cn } from '@/lib/utils';

// Объединяет классы с поддержкой условий
<Button className={cn(
  'base-classes',
  variant === 'primary' && 'primary-classes',
  disabled && 'disabled-classes',
  className // пользовательские классы из props
)} />
```

---

## 📋 Component Patterns

### Compound Components (Glass Card)

```tsx
import { GlassCard, GlassCardHeader, GlassCardContent } from '@/components/glass';

<GlassCard blur="2xl" opacity={5} variant="elevated">
  <GlassCardHeader accent accentColor="lime">
    <h3>Заголовок</h3>
  </GlassCardHeader>
  <GlassCardContent>
    Контент карточки
  </GlassCardContent>
</GlassCard>
```

### Feature Components

```tsx
// features/reviews/ReviewsTable.tsx
export const ReviewsTable = () => {
  const { reviews, loadReviews } = useReviews();
  
  useEffect(() => {
    loadReviews();
  }, []);
  
  return (
    <Table>
      {reviews.map(review => (
        <ReviewRow key={review.id} review={review} />
      ))}
    </Table>
  );
};
```

---

## 🔍 Проверка качества кода

### Pre-build Checklist

- ✅ Все импорты используют alias `@/`
- ✅ Нет неиспользуемых импортов (проверено TypeScript)
- ✅ Нет битых путей (build проходит без ошибок)
- ✅ Все Glass-компоненты используют `backdrop-blur-2xl`
- ✅ Все радиусы `rounded-sm` (2px)
- ✅ Нет градиентов и теней вне Glass-компонентов
- ✅ Цвета только из палитры (`plum`, `lime`, `crimson`, `zinc`)

### Build Commands

```bash
# Development
npm run dev          # Запуск dev server (port 3000)

# Production
npm run build        # Собрать production bundle
npm run preview      # Preview production build

# Type checking
npm run typecheck    # TypeScript type checking без build
```

---

## 📚 Дополнительная документация

- **[SETUP.md](./SETUP.md)** — Инструкции по установке и запуску
- **[CLAUDE.md](./CLAUDE.md)** — Design system rules для AI ассистента
- **[components.json](./components.json)** — shadcn/ui конфигурация

---

## 🐛 Troubleshooting

### Ошибка: "Cannot find module '@/...'"

**Решение**: Перезапустите TypeScript server в IDE
```bash
# VS Code: Cmd/Ctrl + Shift + P → "TypeScript: Restart TS Server"
```

### Ошибка: Glass-компоненты не отображаются

**Решение**: Убедитесь, что импортируете из правильного пути:
```tsx
import { GlassCard } from '@/components/glass'; // ✅
import { GlassCard } from '@/components/ui/glass-card'; // ❌
```

### Ошибка: "Uncaught ReferenceError: process is not defined"

**Решение**: Проверьте `vite.config.ts`, добавьте `define`:
```ts
export default defineConfig({
  define: {
    'process.env': {}
  }
});
```

---

**Последнее обновление**: 2026-10-13  
**Автор**: Kiro AI Agent  
**Версия**: 1.0.0
