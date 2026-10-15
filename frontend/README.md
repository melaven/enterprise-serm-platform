# Tenable SERM Frontend

B2B SaaS Dashboard с premium Glassmorphism дизайном и строгой цветовой палитрой.

## 🎨 Design Philosophy

- **Glassmorphism**: Матовое стекло с backdrop-blur-2xl
- **Royal Elegance**: Глубокий Royal Plum (#43127A) + Electric Lime (#C5FF4A)
- **Многослойные тени**: Отрыв карточек от черного фона
- **Информационная плотность**: Максимум данных без визуального шума

## 🚀 Quick Start

### Development Mode

```bash
# Установка зависимостей
npm install

# Запуск dev сервера
npm run dev
```

Приложение доступно на `http://localhost:5173`

### Production Build

```bash
# Сборка для production
npm run build

# Preview production build
npm run preview
```

### Docker Deployment

**Базовая сборка:**

```bash
# Из корня проекта
cd frontend
docker build -t tenable-serm-frontend:latest .
docker run -p 8080:80 tenable-serm-frontend:latest
```

Приложение доступно на `http://localhost:8080`

**Docker Compose (рекомендуется):**

```bash
# Из корня проекта
docker-compose up -d frontend
```

**Кастомные environment variables:**

```bash
docker run -p 8080:80 \
  -e VITE_API_BASE_URL=https://api.your-domain.com \
  -e VITE_DEMO_MODE=false \
  tenable-serm-frontend:latest
```

**Health Check:**

```bash
curl http://localhost:8080/health
# Ответ: healthy
```

## 🎭 Demo Mode

Frontend поддерживает **Demo Mode** для презентаций и offline разработки:

```bash
# .env
VITE_DEMO_MODE=true
```

**Что происходит в Demo Mode:**

- ✅ Все API запросы используют mock данные
- ✅ 10 реалистичных отзывов (2GIS, Yandex, Google)
- ✅ Полная аналитика (60% positive, 20% neutral, 20% negative)
- ✅ Симуляция сетевых задержек (300-800ms)
- ✅ Автоматический fallback при недоступности backend
- ✅ Квоты, пользователи, JWT токены - всё работает

**Активация:**

```typescript
// Проверка режима
import { isDemoModeActive } from '@/api/demoService';

if (isDemoModeActive()) {
  console.log('Demo mode активен');
}
```

## 📁 Структура проекта

```
frontend/
├── src/
│   ├── api/                    # API layer
│   │   ├── client.ts          # 402/429 HTTP interceptors
│   │   ├── token.ts           # JWT token store
│   │   ├── quota.ts           # 402 Payment Required state
│   │   ├── rateLimit.ts       # 429 Rate Limit state
│   │   ├── services.ts        # API methods
│   │   ├── mockData.ts        # Mock data для demo mode
│   │   ├── demoService.ts     # Smart API wrapper с fallback
│   │   └── index.ts
│   ├── components/
│   │   ├── glass/             # Glassmorphism компоненты
│   │   │   ├── glass-card.tsx
│   │   │   ├── glass-progress.tsx
│   │   │   └── index.ts
│   │   └── ui/                # shadcn/ui компоненты
│   ├── features/              # Feature modules
│   │   ├── auth/
│   │   │   ├── AuthShell.tsx
│   │   │   ├── ProtectedRoute.tsx
│   │   │   └── index.ts
│   │   ├── dashboard/
│   │   │   ├── DashboardLayout.tsx
│   │   │   ├── QuotaWidget.tsx
│   │   │   ├── QuotaModal.tsx
│   │   │   ├── QuotaExceededDialog.tsx
│   │   │   ├── QuotaExceededHost.tsx
│   │   │   ├── RateLimitHost.tsx
│   │   │   └── index.ts
│   │   └── reviews/
│   │       ├── ReviewsTable.tsx
│   │       ├── AnalysisPanel.tsx
│   │       └── index.ts
│   ├── pages/                 # Route pages
│   ├── store/                 # Zustand stores
│   └── lib/                   # Utils
├── Dockerfile                 # Multi-stage production build
├── nginx.conf                 # SPA routing + cache headers
├── .dockerignore             # Оптимизация Docker layers
├── tailwind.config.js         # Дизайн-система
└── package.json
```

## 🎨 Цветовая палитра (Final)

| Название | HEX | RGB | Применение |
|----------|-----|-----|-----------|
| **Black** | `#000000` | rgb(0,0,0) | Основной фон |
| **Royal Plum** | `#43127A` | rgb(67,18,122) | Primary, логотип, акценты |
| **Electric Lime** | `#C5FF4A` | rgb(197,255,74) | Success, прогресс, активные элементы |
| **Crimson** | `#A4172A` | rgb(164,23,42) | Destructive, ошибки, лимиты |
| **Zinc-950** | `#09090b` | - | Фон карточек |
| **Zinc-800** | `#27272a` | - | Borders |
| **White** | `#FFFFFF` | rgb(255,255,255) | Текст, иконки |

## 🔒 Glassmorphism Guidelines

### ✅ ПРАВИЛА

- **Фон**: `bg-white/5` (прозрачный белый 5%)
- **Blur**: `backdrop-blur-2xl` (глубокое размытие)
- **Borders**: `border-white/10` (тонкие рамки 10% opacity)
- **Radius**: `rounded-sm` (2px везде)
- **Shadows**: Многослойные (3 слоя: 4px/8px/16px)

### ❌ ЗАПРЕЩЕНО

- Градиенты (`bg-gradient-*`)
- Неон и Coral (#FF5C5C)
- Любые цвета вне палитры
- Скругления > 2px (кроме `rounded-full`)

### 📐 Пример Glass Card

```tsx
import { GlassCard, GlassCardContent } from '@/components/glass';

<GlassCard blur="2xl" opacity={5} variant="default">
  <GlassCardContent>
    <h3 className="text-white">Title</h3>
    <p className="text-zinc-400">Content</p>
  </GlassCardContent>
</GlassCard>
```

## 🔑 Аутентификация

API client автоматически:
- Извлекает JWT токен из TokenStore
- Добавляет `Authorization: Bearer <token>` во все запросы
- Обрабатывает **401 Unauthorized** (редирект на `/login`)
- Обрабатывает **402 Payment Required** (показ QuotaExceededDialog)
- Обрабатывает **429 Too Many Requests** (показ RateLimitHost с таймером)
- Fallback на mock данные при недоступности backend

### Пример использования

```typescript
import { apiClient, tokens } from '@/api/services';
import * as demoApi from '@/api/demoService';

// Login (с demo fallback)
const response = await demoApi.login({ 
  email: 'test@example.com', 
  password: 'TestPassword123!' 
});

tokens.set(response.access_token);

// Все последующие запросы с токеном
const reviews = await demoApi.getReviews({ limit: 20 });

// Проверить токен
if (tokens.get()) {
  // User is authenticated
}

// Logout
await demoApi.logout();
tokens.clear();
```

## 📦 Основные компоненты

### Glass Components

**GlassCard** - Premium glass карточка:

```tsx
import { GlassCard, GlassCardContent, GlassCardHeader, GlassCardFooter } from '@/components/glass';

<GlassCard blur="2xl" opacity={5} variant="default" hover>
  <GlassCardHeader accent accentColor="lime">
    <h3 className="text-white">Title</h3>
  </GlassCardHeader>
  <GlassCardContent>
    <p className="text-zinc-400">Content</p>
  </GlassCardContent>
  <GlassCardFooter>
    <Button>Action</Button>
  </GlassCardFooter>
</GlassCard>
```

**GlassProgress** - Прогресс бар:

```tsx
import { GlassProgress, GlassCircularProgress } from '@/components/glass';

<GlassProgress 
  value={75} 
  label="Квота LLM токенов"
  showPercent 
  fillColor="bg-lime"
/>

<GlassCircularProgress 
  value={60} 
  size={120}
  label="Загрузка"
/>
```

### Dashboard Components

**DashboardLayout** - Главный layout с sidebar:

```tsx
import { DashboardLayout } from '@/features/dashboard';

<DashboardLayout
  title="Аналитика"
  userEmail="user@example.com"
  quota={{ 
    llmTokens: { used: 125000, limit: 500000 },
    reviewsParsed: { used: 8234, limit: 10000 },
    resetDate: '2026-12-31'
  }}
  online={true}
  onLogout={() => logout()}
  onUpgrade={() => navigate('/billing')}
>
  {/* Your content */}
</DashboardLayout>
```

**QuotaWidget** - Виджет квот в sidebar:

```tsx
import { QuotaWidget } from '@/features/dashboard';

<QuotaWidget
  llmTokens={{ used: 125000, limit: 500000 }}
  reviewsParsed={{ used: 8234, limit: 10000 }}
  resetDate="2026-12-31"
  onUpgrade={() => navigate('/billing')}
  compact  // Узкий режим для sidebar
/>
```

### Модальные окна

**QuotaExceededDialog** - HTTP 402:

```tsx
import { QuotaExceededDialog } from '@/features/dashboard';

<QuotaExceededDialog
  open={isOpen}
  onOpenChange={setIsOpen}
  info={{
    code: 'llm_tokens_exceeded',
    message: 'Лимит LLM токенов исчерпан',
    requestsUsed: 500000,
    maxRequests: 500000,
    resetDate: '2026-12-31',
    correlationId: 'abc-123'
  }}
  onUpgrade={() => navigate('/billing')}
/>
```

**RateLimitHost** - HTTP 429 таймер:

```tsx
import { RateLimitHost } from '@/features/dashboard';

// Монтируется ОДИН раз в корне (main.tsx)
<RateLimitHost />
```

## 📚 Документация

Полная документация дизайн-системы: [CLAUDE.md](./CLAUDE.md)

## 🛠️ Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool (HMR, optimized bundles)
- **Tailwind CSS** - Utility-first CSS
- **Zustand** - State management
- **React Router v6** - Client-side routing
- **Axios** - HTTP client с interceptors
- **Radix UI** - Headless UI components (Dialog, etc.)
- **shadcn/ui** - Pre-built accessible components
- **Lucide React** - Icon library
- **Sonner** - Toast notifications
- **@fontsource** - Local fonts (Inter, JetBrains Mono)

## 🔧 Environment Variables

Создайте `.env` на основе `.env.example`:

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:8000

# Demo Mode (для презентаций и offline разработки)
VITE_DEMO_MODE=false
```

**Production:**

```bash
VITE_API_BASE_URL=https://api.your-domain.com
VITE_DEMO_MODE=false
```

**Demo/Presentation:**

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_DEMO_MODE=true
```

## 📝 Coding Guidelines

1. **TypeScript strict mode** - никогда не используй `any`
2. **Glassmorphism** - всегда `backdrop-blur-2xl`, `bg-white/5`, `border-white/10`
3. **Цветовая палитра** - только Royal Plum, Electric Lime, Crimson
4. **Адаптивность** - mobile-first (sm → md → lg)
5. **Accessibility** - ARIA labels, focus states, keyboard navigation
6. **Barrel exports** - используй `index.ts` для экспорта из папок
7. **Path alias** - всегда `@/` вместо относительных путей
8. **Demo mode** - все API методы должны работать через `demoService.ts`

## 📱 Responsive Design

Tailwind breakpoints:

- **xs**: < 640px (mobile)
- **sm**: ≥ 640px (tablet portrait)
- **md**: ≥ 768px (tablet landscape, small laptop)
- **lg**: ≥ 1024px (desktop)
- **xl**: ≥ 1280px (large desktop)

### Adaptive Guidelines

- **Padding**: `p-4` → `sm:p-6` → `md:p-8`
- **Grid**: `grid-cols-1` → `sm:grid-cols-2` → `md:grid-cols-3`
- **Flex direction**: `flex-col` → `sm:flex-row`
- **Buttons**: `w-full` → `sm:w-auto`
- **Sidebar**: `hidden` → `md:flex`

## 🐳 Docker Production Deployment

**Dockerfile структура:**

```dockerfile
# Stage 1: Build (node:20-alpine)
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit
COPY . .
RUN npm run build

# Stage 2: Serve (nginx:1.25-alpine)
FROM nginx:1.25-alpine
COPY nginx.conf /etc/nginx/conf.d/
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Nginx конфигурация:**

- ✅ SPA routing: `try_files $uri $uri/ /index.html`
- ✅ Gzip compression для JS/CSS/JSON
- ✅ Cache-Control: 1 year для hashed assets, no-store для index.html
- ✅ Security headers: X-Frame-Options, X-Content-Type-Options, CSP
- ✅ Health check endpoint: `/health`

**Docker размеры:**

- Build stage: ~500 MB (node:20-alpine)
- Production image: ~50 MB (nginx:1.25-alpine + dist)
- Compressed dist: ~120 KB JS + ~20 KB CSS (gzip)

## 🚀 Deployment Workflow

```bash
# 1. Build Docker image
docker build -t tenable-serm-frontend:v1.0.0 .

# 2. Tag для registry
docker tag tenable-serm-frontend:v1.0.0 registry.example.com/serm-frontend:v1.0.0

# 3. Push to registry
docker push registry.example.com/serm-frontend:v1.0.0

# 4. Deploy на production
kubectl apply -f k8s/frontend-deployment.yaml
# или
docker-compose -f docker-compose.prod.yml up -d frontend
```

## 🧪 Testing

```bash
# Unit tests (TODO)
npm run test

# E2E tests (TODO)
npm run test:e2e

# Type check
npx tsc --noEmit

# Lint
npm run lint
```

## 📄 License

Proprietary - Tenable SERM


## 📚 Документация

- **FRONTEND_ARCHITECTURE.md** - Полная архитектура фронтенда
- **BUILD_MANIFEST.md** - Production build чеклист
- **tailwind.config.js** - Конфигурация дизайн-системы

## 🔗 Полезные ссылки

- [Tailwind CSS](https://tailwindcss.com/docs)
- [Radix UI](https://www.radix-ui.com/primitives/docs/overview/introduction)
- [shadcn/ui](https://ui.shadcn.com/)
- [Lucide Icons](https://lucide.dev/icons/)
- [Zustand](https://docs.pmnd.rs/zustand/getting-started/introduction)

## 📄 License

Proprietary - Tenable SERM © 2026

---

**Production Ready** ✅
- Docker multi-stage build
- Nginx optimized configuration
- Mobile responsive (sm/md/lg breakpoints)
- Demo mode для презентаций
- 402/429 HTTP error handling
- Glassmorphism pixel-perfect
