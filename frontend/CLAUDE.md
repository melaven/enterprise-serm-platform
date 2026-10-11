# Design System Rules — Tenable SERM B2B Dashboard

## Философия дизайна

Утилитарный flat-design для B2B SaaS с максимальным фокусом на информационной плотности и читаемости.

**Принципы:**
- Никаких украшательств — только функциональность
- Информация важнее эстетики
- Высокий контраст для работы в разных условиях освещения
- Консистентность > креативность

---

## 🎨 Цветовая палитра (СТРОГО)

### Основные цвета

```typescript
const colors = {
  ink: '#0B0B0F',        // Фон, темные поверхности
  chrome: '#C9CED6',     // Текст, границы, неактивные элементы
  plum: '#5A189A',       // Primary actions, навигация
  lime: '#C5FF4A',       // Акценты, статусы, графики
}
```

### Правила использования

| Элемент | Цвет | Пример использования |
|---------|------|---------------------|
| **Фон приложения** | `bg-ink` | Основной фон дашборда |
| **Карточки/панели** | `bg-ink-50` | Слегка светлее основного фона |
| **Основной текст** | `text-chrome-300` | Параграфы, лейблы |
| **Вторичный текст** | `text-chrome-500` | Плейсхолдеры, описания |
| **Границы** | `border-chrome-600` | Borders всех элементов |
| **Primary кнопки** | `bg-plum hover:bg-plum-400` | CTA, submit buttons |
| **Активная навигация** | `bg-plum text-white` | Выбранный пункт меню |
| **Success статусы** | `bg-lime text-ink` | Успешные операции |
| **Бейджи/теги** | `bg-lime-900 text-lime` | Статус-теги, лейблы |

### 🚫 ЗАПРЕЩЕНО

- ❌ Использовать любые цвета вне палитры (ink, chrome, plum, lime)
- ❌ Использовать градиенты (`bg-gradient-*`)
- ❌ Использовать прозрачность для эффекта стекла (`bg-opacity-*` с backdrop-blur)
- ❌ Создавать цветовые вариации "на глаз"

---

## 📐 Геометрия и структура

### Скругления (Border Radius)

```css
/* МАКСИМАЛЬНОЕ скругление — 2px */
rounded-none    /* 0px - предпочтительно для карточек, инпутов */
rounded-sm      /* 2px - максимум для кнопок, бейджей */
rounded-full    /* только для аватаров и индикаторов */
```

**Правило:** По умолчанию используй `rounded-none`. Используй `rounded-sm` только если элемент требует визуального "смягчения" (кнопки, теги).

### Границы (Borders)

```css
/* Стандартная толщина границ */
border          /* 1px - по умолчанию */
border-2        /* 2px - для фокуса, активных состояний */

/* Цвет границ */
border-chrome-600   /* Стандартные границы */
border-plum         /* Активные/фокус состояния */
border-lime         /* Акцентные границы (предупреждения, успех) */
```

### 🚫 ЗАПРЕЩЕНО

- ❌ `shadow-*` — любые классы теней КАТЕГОРИЧЕСКИ запрещены
- ❌ `backdrop-blur-*` — эффекты размытия запрещены
- ❌ `rounded-md`, `rounded-lg`, `rounded-xl` — скругления больше 2px запрещены
- ❌ `border-3` или больше — максимум 2px

---

## 📝 Типографика

### Шрифты

```typescript
font-sans   // Inter — основной шрифт для UI
font-mono   // JetBrains Mono — для кода, технических данных
```

### Размеры текста

| Применение | Класс | Размер | Line Height |
|-----------|-------|--------|-------------|
| Мелкий текст (метаданные) | `text-xs` | 11px | 16px |
| Описания, вторичный текст | `text-sm` | 13px | 20px |
| Основной текст | `text-base` | 14px | 22px |
| Подзаголовки | `text-lg` | 16px | 24px |
| Заголовки секций | `text-xl` | 20px | 28px |
| Заголовки страниц | `text-2xl` | 24px | 32px |
| Hero заголовки | `text-3xl` | 32px | 40px |

### Цвета текста

```css
text-chrome-300    /* Основной текст — высокий контраст */
text-chrome-400    /* Менее важный текст */
text-chrome-500    /* Плейсхолдеры, деактивированный текст */
text-plum          /* Ссылки, интерактивные элементы */
text-lime          /* Акцентный текст (статусы, метрики) */
text-white         /* Текст на темных кнопках/фонах */
```

### Начертание

```css
font-normal      /* 400 — основной текст */
font-medium      /* 500 — подзаголовки, лейблы */
font-semibold    /* 600 — заголовки, важные элементы */
```

### 🚫 ЗАПРЕЩЕНО

- ❌ `font-light` (300) — слишком низкий контраст
- ❌ `font-bold` (700) и `font-extrabold` (800) — слишком агрессивно для B2B
- ❌ Использовать `text-gray-*` вместо `text-chrome-*`

---

## 🎯 Компоненты

### Кнопки

#### Primary Button (основное действие)
```tsx
<button className="
  bg-plum hover:bg-plum-400 active:bg-plum-600
  text-white font-medium text-sm
  px-4 py-2
  border-2 border-transparent
  rounded-sm
  transition-colors duration-150
">
  Submit
</button>
```

#### Secondary Button
```tsx
<button className="
  bg-transparent hover:bg-ink-50
  text-chrome-300 hover:text-white
  font-medium text-sm
  px-4 py-2
  border-2 border-chrome-600 hover:border-chrome-400
  rounded-sm
  transition-colors duration-150
">
  Cancel
</button>
```

#### Ghost Button (для навигации)
```tsx
<button className="
  bg-transparent hover:bg-plum-900/20
  text-chrome-400 hover:text-plum
  font-medium text-sm
  px-3 py-1.5
  rounded-none
  transition-colors duration-150
">
  View Details
</button>
```

### Input поля

```tsx
<input
  type="text"
  className="
    w-full
    bg-ink-50
    text-chrome-300 placeholder:text-chrome-500
    border border-chrome-600 focus:border-plum
    rounded-none
    px-3 py-2
    text-sm
    outline-none
    transition-colors duration-150
  "
  placeholder="Enter value..."
/>
```

### Карточки/Панели

```tsx
<div className="
  bg-ink-50
  border border-chrome-600
  rounded-none
  p-6
">
  {/* Содержимое карточки */}
</div>
```

### Бейджи/Статусы

```tsx
// Success Badge
<span className="
  inline-flex items-center
  bg-lime text-ink
  px-2 py-0.5
  rounded-sm
  text-xs font-medium
">
  Active
</span>

// Info Badge
<span className="
  inline-flex items-center
  bg-plum-900 text-plum-300
  border border-plum-700
  px-2 py-0.5
  rounded-sm
  text-xs font-medium
">
  Processing
</span>

// Neutral Badge
<span className="
  inline-flex items-center
  bg-transparent text-chrome-400
  border border-chrome-600
  px-2 py-0.5
  rounded-sm
  text-xs font-medium
">
  Pending
</span>
```

### Таблицы

```tsx
<table className="w-full">
  <thead>
    <tr className="border-b-2 border-chrome-600">
      <th className="text-left text-xs font-semibold text-chrome-400 uppercase tracking-wider px-4 py-3">
        Column
      </th>
    </tr>
  </thead>
  <tbody>
    <tr className="border-b border-chrome-600/50 hover:bg-ink-50 transition-colors">
      <td className="px-4 py-3 text-sm text-chrome-300">
        Data
      </td>
    </tr>
  </tbody>
</table>
```

---

## 📏 Spacing & Layout

### Grid система

```css
/* Основная сетка дашборда */
gap-4    /* 16px между элементами */
gap-6    /* 24px между секциями */
gap-8    /* 32px между крупными блоками */

/* Отступы внутри компонентов */
p-3      /* 12px - мелкие элементы (бейджи, кнопки) */
p-4      /* 16px - средние компоненты (инпуты, карточки) */
p-6      /* 24px - крупные панели */
p-8      /* 32px - страничные контейнеры */
```

### Container

```tsx
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
  {/* Основной контент */}
</div>
```

---

## 🔒 Правила для AI Code Generation

### ОБЯЗАТЕЛЬНЫЕ правила при генерации кода

1. **Все компоненты ДОЛЖНЫ использовать только цвета из палитры:**
   - `ink`, `chrome`, `plum`, `lime` и их оттенки
   
2. **НИКОГДА не использовать:**
   - `shadow-*` классы
   - `bg-gradient-*` классы
   - `backdrop-blur-*` классы
   - Скругления больше `rounded-sm` (кроме `rounded-full` для кругов)

3. **Всегда проверять:**
   - Контрастность текста (минимум WCAG AA)
   - Доступность интерактивных элементов (focus states)
   - Консистентность spacing (использовать шкалу 4px)

4. **Предпочитаемые паттерны:**
   - Границы вместо теней для разделения
   - Прямые углы (`rounded-none`) для серьезного B2B look
   - Высокий контраст для читаемости

### Checklist перед коммитом компонента

- [ ] Нет `shadow-*` классов
- [ ] Нет `backdrop-blur-*` классов
- [ ] Нет градиентов
- [ ] Скругления ≤ 2px (кроме `rounded-full`)
- [ ] Используются только цвета палитры
- [ ] Есть hover/focus/active состояния
- [ ] Текст контрастный и читаемый
- [ ] Spacing кратен 4px

---

## 📦 Примеры готовых компонентов

### Dashboard Card

```tsx
interface DashboardCardProps {
  title: string;
  value: string | number;
  trend?: 'up' | 'down';
  trendValue?: string;
}

export const DashboardCard = ({ title, value, trend, trendValue }: DashboardCardProps) => {
  return (
    <div className="bg-ink-50 border border-chrome-600 rounded-none p-6">
      <p className="text-xs font-medium text-chrome-500 uppercase tracking-wider mb-2">
        {title}
      </p>
      <p className="text-3xl font-semibold text-chrome-300 mb-3">
        {value}
      </p>
      {trend && trendValue && (
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${
            trend === 'up' ? 'text-lime' : 'text-chrome-400'
          }`}>
            {trend === 'up' ? '↑' : '↓'} {trendValue}
          </span>
          <span className="text-xs text-chrome-500">vs last period</span>
        </div>
      )}
    </div>
  );
};
```

### Loading State

```tsx
export const LoadingSpinner = () => {
  return (
    <div className="flex items-center justify-center p-8">
      <div className="w-8 h-8 border-2 border-chrome-600 border-t-plum rounded-full animate-spin" />
    </div>
  );
};
```

### Alert Component

```tsx
interface AlertProps {
  type: 'success' | 'error' | 'info';
  message: string;
}

export const Alert = ({ type, message }: AlertProps) => {
  const styles = {
    success: 'bg-lime-900 border-lime text-lime',
    error: 'bg-red-900/20 border-red-500 text-red-400',
    info: 'bg-plum-900 border-plum-700 text-plum-300',
  };

  return (
    <div className={`border-2 rounded-sm px-4 py-3 ${styles[type]}`}>
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
};
```

---

## 🚀 Getting Started

### 1. Установка зависимостей

```bash
npm install axios
npm install -D tailwindcss postcss autoprefixer
npm install -D @types/node
```

### 2. Инициализация Tailwind

```bash
npx tailwindcss init -p
```

### 3. Импорт в главный CSS

```css
/* src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Глобальные стили */
body {
  @apply bg-ink text-chrome-300 font-sans antialiased;
}
```

### 4. Использование API client

```typescript
import apiClient, { auth } from './api/client';

// После логина
auth.setToken(response.data.access_token);

// Выполнение запросов (токен добавится автоматически)
const reviews = await apiClient.get('/api/v1/reviews');

// Логаут
auth.clearToken();
```

---

## 📚 Дополнительные ресурсы

- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [Axios Documentation](https://axios-http.com/docs/intro)
- [WCAG Contrast Guidelines](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)

---

**Версия:** 1.0  
**Последнее обновление:** 2026-10-11  
**Мейнтейнер:** Tenable SERM Team
