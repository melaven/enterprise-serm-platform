# Инструкция по установке и запуску Frontend

## 📋 Предварительные требования

- Node.js >= 18.0.0
- npm >= 9.0.0 (или yarn/pnpm)

## 🚀 Быстрый старт

### 1. Перейти в директорию frontend

```bash
cd frontend
```

### 2. Установить зависимости

```bash
npm install
```

### 3. Создать файл `.env`

```bash
cp .env.example .env
```

Отредактируйте `.env` и укажите URL вашего бэкенда:

```
VITE_API_BASE_URL=http://localhost:8000
```

### 4. Запустить dev сервер

```bash
npm run dev
```

Приложение будет доступно на: **http://localhost:3000**

## 📦 Команды

| Команда | Описание |
|---------|----------|
| `npm run dev` | Запуск dev сервера с hot-reload |
| `npm run build` | Production сборка |
| `npm run preview` | Предпросмотр production сборки |
| `npm run lint` | Проверка кода с ESLint |

## 🎨 Дизайн-система

Перед началом работы **ОБЯЗАТЕЛЬНО** прочитайте:
- [CLAUDE.md](./CLAUDE.md) - Полная документация дизайн-системы
- [README.md](./README.md) - Общая информация о проекте

### Ключевые правила

✅ **РАЗРЕШЕНО:**
- Цвета: `ink`, `chrome`, `plum`, `lime`
- Скругления: `rounded-none`, `rounded-sm` (max 2px)
- Границы для разделения элементов

❌ **ЗАПРЕЩЕНО:**
- `shadow-*` классы
- `bg-gradient-*` классы
- `backdrop-blur-*` классы
- Скругления > 2px

## 🔑 Работа с аутентификацией

Все запросы к API автоматически получают JWT токен из localStorage.

### Пример использования

```typescript
import apiClient, { auth } from '@/api/client';

// Логин
const response = await apiClient.post('/api/v1/auth/login', {
  email: 'user@example.com',
  password: 'password'
});

// Сохранить токен
auth.setToken(response.data.access_token);

// Теперь все запросы будут с Authorization: Bearer <token>
const reviews = await apiClient.get('/api/v1/reviews');

// Логаут
auth.clearToken();
```

## 🐛 Troubleshooting

### Ошибка "Cannot find module"

```bash
# Удалить node_modules и переустановить
rm -rf node_modules package-lock.json
npm install
```

### CORS ошибки

Убедитесь, что бэкенд настроен на прием запросов с `http://localhost:3000`:

```python
# В FastAPI (app/main.py)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Tailwind классы не применяются

1. Проверьте, что в `tailwind.config.js` указаны правильные пути:
   ```js
   content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"]
   ```

2. Перезапустите dev сервер:
   ```bash
   npm run dev
   ```

## 📂 Структура проекта

```
frontend/
├── src/
│   ├── api/              # API клиенты
│   │   ├── client.ts     # Axios + JWT interceptor
│   │   └── types.ts      # TypeScript types
│   ├── components/       # UI компоненты
│   │   └── Button.tsx
│   ├── App.tsx           # Главный компонент
│   ├── main.tsx          # Entry point
│   └── index.css         # Tailwind + глобальные стили
├── public/               # Статические файлы
├── index.html            # HTML template
├── tailwind.config.js    # Tailwind конфигурация
├── vite.config.ts        # Vite конфигурация
├── tsconfig.json         # TypeScript конфигурация
├── package.json
├── CLAUDE.md             # Документация дизайн-системы
└── README.md             # Общая информация
```

## 🔗 Полезные ссылки

- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [Vite](https://vitejs.dev)
- [Axios](https://axios-http.com)
- [TypeScript](https://www.typescriptlang.org)

## 📞 Поддержка

При возникновении проблем:
1. Проверьте [CLAUDE.md](./CLAUDE.md) - там есть Troubleshooting секция
2. Проверьте console в браузере на наличие ошибок
3. Убедитесь, что бэкенд запущен и доступен

---

**Успешной разработки! 🚀**
