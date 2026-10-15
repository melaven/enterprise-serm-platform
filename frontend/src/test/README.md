# Frontend Test Suite

Надежный тестовый контур для Tenable SERM Frontend.

## 🎯 Охват тестирования

### Критические компоненты (100% coverage target)

1. **GlobalErrorBoundary** (`components/error/__tests__/`)
   - ✅ Error catching и recovery
   - ✅ Premium error screen rendering
   - ✅ DEV vs Production mode behavior
   - ✅ Reload и reset actions

2. **AsyncView** (`components/ui/__tests__/`)
   - ✅ 4 состояния: loading, error, empty, success
   - ✅ State transitions
   - ✅ State priority (loading > error > empty > content)
   - ✅ Accessibility

3. **useAppStore** (`store/__tests__/`)
   - ✅ Auth actions (login, register, logout)
   - ✅ Token management
   - ✅ Loading states
   - ✅ Error handling

4. **DemoService** (`api/__tests__/`)
   - ✅ Demo Mode activation
   - ✅ API fallback on error
   - ✅ Mock data filtering
   - ✅ Network delay simulation

## 🚀 Запуск тестов

### Watch Mode (разработка)
```bash
npm run test
# или
npm test
```

### Single Run (CI/CD)
```bash
npm run test:run
```

### UI Mode (интерактивный)
```bash
npm run test:ui
```

### Coverage Report
```bash
npm run test:coverage
```

## 📊 Ожидаемые результаты

```
Test Files  4 passed (4)
     Tests  45 passed (45)
  Start at  14:30:00
  Duration  2.5s
```

### Coverage Targets

| Component            | Statements | Branches | Functions | Lines |
|---------------------|------------|----------|-----------|-------|
| GlobalErrorBoundary | 100%       | 100%     | 100%      | 100%  |
| AsyncView           | 100%       | 100%     | 100%      | 100%  |
| useAppStore         | 95%+       | 90%+     | 95%+      | 95%+  |
| demoService         | 95%+       | 85%+     | 95%+      | 95%+  |

## 🛠️ Технологии

- **Vitest** — быстрый тестовый runner (Vite-native)
- **@testing-library/react** — React компонент тестирование
- **@testing-library/jest-dom** — дополнительные matchers
- **jsdom** — DOM environment для Node.js

## 📝 Структура тестов

```
src/
├── api/
│   └── __tests__/
│       └── demoService.test.ts
├── components/
│   ├── error/
│   │   └── __tests__/
│   │       └── GlobalErrorBoundary.test.tsx
│   └── ui/
│       └── __tests__/
│           └── async-view.test.tsx
├── store/
│   └── __tests__/
│       └── useAppStore.test.ts
└── test/
    ├── setup.ts
    └── README.md
```

## 🎨 Best Practices

### 1. Описательные имена тестов

```typescript
it('should catch error and render error screen', () => {
  // Понятно что тестируется
});
```

### 2. AAA Pattern (Arrange, Act, Assert)

```typescript
it('should login successfully', async () => {
  // Arrange
  const mockResponse = { ... };
  vi.mocked(api.login).mockResolvedValueOnce(mockResponse);
  
  // Act
  await act(async () => {
    await result.current.performLogin('email', 'pass');
  });
  
  // Assert
  expect(result.current.isAuthenticated).toBe(true);
});
```

### 3. Cleanup

```typescript
beforeEach(() => {
  vi.clearAllMocks();
  useAppStore.setState({ /* reset state */ });
});
```

### 4. Accessibility Testing

```typescript
expect(screen.getByRole('button', { name: /reload/i })).toBeInTheDocument();
```

## 🔍 Debugging

### Вывод DOM дерева

```typescript
import { screen } from '@testing-library/react';
screen.debug(); // Print entire DOM
```

### Проверка рендеринга

```typescript
const { container } = render(<Component />);
console.log(container.innerHTML);
```

### Watch specific test

```bash
npm test -- GlobalErrorBoundary
```

## ⚡ Performance

- **Параллельные запуски:** Vitest запускает тесты параллельно
- **Изоляция:** Каждый тест изолирован (cleanup после каждого)
- **Fast refresh:** Watch mode с hot reload

## 🚨 CI/CD Integration

### Pre-commit Hook

```bash
npm run test:run
# Должен пройти перед коммитом
```

### GitHub Actions

```yaml
- name: Run Tests
  run: npm run test:run
  
- name: Coverage Report
  run: npm run test:coverage
```

## 📚 Дополнительные ресурсы

- [Vitest Documentation](https://vitest.dev/)
- [Testing Library Best Practices](https://testing-library.com/docs/queries/about)
- [React Testing Patterns](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
