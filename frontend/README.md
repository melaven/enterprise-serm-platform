# Tenable SERM Frontend

B2B SaaS Dashboard с утилитарным flat-design и строгой дизайн-системой.

## 🎨 Design Philosophy

- **Утилитарность**: функциональность > эстетика
- **Flat Design**: без теней, градиентов, эффектов стекла
- **Высокий контраст**: читаемость в любых условиях
- **Информационная плотность**: максимум данных без визуального шума

## 🚀 Quick Start

### Установка зависимостей

```bash
npm install
```

### Запуск dev сервера

```bash
npm run dev
```

Приложение будет доступно на `http://localhost:3000`

### Сборка для production

```bash
npm run build
```

## 📁 Структура проекта

```
frontend/
├── src/
│   ├── api/              # API клиенты и типы
│   │   ├── client.ts     # Axios instance с JWT interceptor
│   │   └── types.ts      # TypeScript типы для API
│   ├── components/       # Переиспользуемые UI компоненты
│   │   └── Button.tsx
│   └── index.css         # Глобальные стили и Tailwind
├── tailwind.config.js    # Конфигурация дизайн-системы
├── CLAUDE.md             # Полная документация дизайн-системы
└── package.json
```

## 🎨 Цветовая палитра

| Название | HEX | Применение |
|----------|-----|-----------|
| **Ink** | `#0B0B0F` | Основной фон |
| **Chrome** | `#C9CED6` | Текст, границы |
| **Royal Plum** | `#5A189A` | Primary actions |
| **Electric Lime** | `#C5FF4A` | Акценты, статусы |

## 🔒 Строгие ограничения

### ❌ ЗАПРЕЩЕНО

- Любые тени (`shadow-*`)
- Градиенты (`bg-gradient-*`)
- Blur эффекты (`backdrop-blur-*`)
- Скругления > 2px (кроме `rounded-full` для кругов)
- Цвета вне палитры

### ✅ РАЗРЕШЕНО

- `rounded-none` или `rounded-sm` (max 2px)
- Границы для разделения элементов
- Высококонтрастный текст
- Плоские цвета из палитры

## 🔑 Аутентификация

API клиент автоматически:
- Извлекает JWT токен из `localStorage`
- Добавляет `Authorization: Bearer <token>` во все запросы
- Обрабатывает 401 ошибки (редирект на `/login`)
- Обрабатывает 403 ошибки (RLS блокировка)

### Пример использования

```typescript
import apiClient, { auth } from '@/api/client';

// Сохранить токен после логина
auth.setToken(response.data.access_token);

// Все последующие запросы будут с токеном
const reviews = await apiClient.get('/api/v1/reviews');

// Проверить наличие токена
if (auth.hasToken()) {
  // User is authenticated
}

// Выход
auth.clearToken();
```

## 📦 Основные компоненты

### Button

```tsx
import { Button } from '@/components/Button';

<Button variant="primary">Submit</Button>
<Button variant="secondary">Cancel</Button>
<Button variant="ghost">View Details</Button>
```

### Input Field

```tsx
<input 
  type="text" 
  className="input-field" 
  placeholder="Enter value..."
/>
```

### Card/Panel

```tsx
<div className="card p-6">
  <h3 className="text-lg font-semibold text-chrome-300">Title</h3>
  <p className="text-sm text-chrome-400">Content</p>
</div>
```

### Badge

```tsx
<span className="badge-success">Active</span>
<span className="badge-info">Processing</span>
<span className="badge-neutral">Pending</span>
```

## 📚 Документация

Полная документация дизайн-системы: [CLAUDE.md](./CLAUDE.md)

## 🛠️ Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **React Router** - Navigation (to be added)

## 🔧 Environment Variables

Создайте файл `.env` на основе `.env.example`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## 📝 Coding Guidelines

1. **Всегда используй TypeScript** - никакого `any`
2. **Следуй дизайн-системе** - проверяй CLAUDE.md перед созданием компонентов
3. **Переиспользуй компоненты** - не дублируй код
4. **Accessibility first** - всегда добавляй focus states и ARIA атрибуты
5. **Mobile-first** - начинай с мобильной версии

## 🧪 Testing (TODO)

```bash
npm run test
```

## 📄 License

Proprietary - Tenable SERM
