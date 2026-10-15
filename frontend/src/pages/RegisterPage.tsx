import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store/useAppStore';

/**
 * RegisterPage — строгая flat-форма регистрации на bg-ink-950
 * 
 * Интеграция:
 * - useAppStore.performRegister() для API /api/v1/auth/register
 * - Сохранение токена и пользователя
 * - Редирект на /dashboard при успехе
 * - Валидация пароля и email
 */
export function RegisterPage() {
  const navigate = useNavigate();
  const { performRegister, isAuthenticated } = useAppStore();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Если уже залогинен, редирект на главную
  if (isAuthenticated) {
    navigate('/');
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    
    // Валидация
    if (!email.trim() || !password.trim()) {
      toast.error('Заполните все обязательные поля');
      return;
    }

    if (password.length < 8) {
      toast.error('Пароль должен содержать минимум 8 символов');
      return;
    }

    if (password !== confirmPassword) {
      toast.error('Пароли не совпадают');
      return;
    }

    setIsLoading(true);
    
    try {
      const success = await performRegister(email, password, fullName || undefined);
      
      if (success) {
        toast.success('Регистрация завершена', {
          description: `Добро пожаловать в Tenable SERM!`,
        });
        navigate('/');
      } else {
        toast.error('Ошибка регистрации', {
          description: 'Возможно, этот email уже используется',
        });
      }
    } catch (error) {
      toast.error('Ошибка сети', {
        description: error instanceof Error ? error.message : 'Не удалось подключиться к серверу',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4">
      <div className="w-full max-w-md space-y-8">
        {/* Логотип / Название */}
        <div className="text-center">
          <h1 className="text-4xl font-bold text-white">
            Tenable <span className="text-plum">SERM</span>
          </h1>
          <p className="mt-3 text-chrome-400">Система управления электронной репутацией</p>
        </div>

        {/* Форма регистрации */}
        <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-8">
          <h2 className="mb-6 text-2xl font-semibold text-white">Регистрация</h2>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="fullName" className="block text-sm font-medium text-chrome-300">
                Полное имя <span className="text-chrome-500">(опционально)</span>
              </label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Иван Иванов"
                disabled={isLoading}
                className="w-full rounded-sm border-2 border-chrome-600 bg-ink-950 px-4 py-2.5 text-white placeholder:text-chrome-500 transition-colors focus:border-plum focus:outline-none disabled:opacity-50"
                autoComplete="name"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-chrome-300">
                Email <span className="text-destructive">*</span>
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                disabled={isLoading}
                className="w-full rounded-sm border-2 border-chrome-600 bg-ink-950 px-4 py-2.5 text-white placeholder:text-chrome-500 transition-colors focus:border-plum focus:outline-none disabled:opacity-50"
                autoComplete="email"
                required
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-medium text-chrome-300">
                Пароль <span className="text-destructive">*</span>
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Минимум 8 символов"
                disabled={isLoading}
                className="w-full rounded-sm border-2 border-chrome-600 bg-ink-950 px-4 py-2.5 text-white placeholder:text-chrome-500 transition-colors focus:border-plum focus:outline-none disabled:opacity-50"
                autoComplete="new-password"
                minLength={8}
                required
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-chrome-300">
                Подтвердите пароль <span className="text-destructive">*</span>
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Повторите пароль"
                disabled={isLoading}
                className="w-full rounded-sm border-2 border-chrome-600 bg-ink-950 px-4 py-2.5 text-white placeholder:text-chrome-500 transition-colors focus:border-plum focus:outline-none disabled:opacity-50"
                autoComplete="new-password"
                minLength={8}
                required
              />
            </div>

            <Button
              type="submit"
              variant="default"
              size="lg"
              disabled={isLoading}
              className="w-full"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Регистрация...
                </>
              ) : (
                'Зарегистрироваться'
              )}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-chrome-400">
            Уже есть аккаунт?{' '}
            <button
              type="button"
              onClick={() => navigate('/login')}
              className="font-medium text-plum hover:text-plum-400 transition-colors"
            >
              Войти
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-chrome-500">
          © 2026 Tenable SERM. Все права защищены.
        </p>
      </div>
    </div>
  );
}
