import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store/useAppStore';

/**
 * LoginPage — строгая flat-форма входа на bg-ink-950
 * 
 * Интеграция:
 * - useAppStore.performLogin() для API /api/v1/auth/login
 * - Сохранение токена и пользователя
 * - Редирект на /dashboard при успехе
 * - Аккуратные ошибки через sonner toast
 */
export function LoginPage() {
  const navigate = useNavigate();
  const { performLogin, isAuthenticated } = useAppStore();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Если уже залогинен, редирект на главную
  if (isAuthenticated) {
    navigate('/');
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    
    if (!email.trim() || !password.trim()) {
      toast.error('Заполните все поля');
      return;
    }

    setIsLoading(true);
    
    try {
      const success = await performLogin(email, password);
      
      if (success) {
        toast.success('Вход выполнен', {
          description: `Добро пожаловать, ${email}`,
        });
        navigate('/');
      } else {
        toast.error('Ошибка входа', {
          description: 'Проверьте email и пароль',
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
            Tenable <span className="bg-plum px-2 text-white">SERM</span>
          </h1>
          <p className="mt-3 text-chrome-400">Аналитика оценок и качества сервиса</p>
        </div>

        {/* Форма входа */}
        <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-8">
          <h2 className="mb-6 text-2xl font-semibold text-white">Вход</h2>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-chrome-300">
                Email
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
                Пароль
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={isLoading}
                className="w-full rounded-sm border-2 border-chrome-600 bg-ink-950 px-4 py-2.5 text-white placeholder:text-chrome-500 transition-colors focus:border-plum focus:outline-none disabled:opacity-50"
                autoComplete="current-password"
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
                  Вход...
                </>
              ) : (
                'Войти'
              )}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-chrome-400">
            Нет аккаунта?{' '}
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="font-medium text-plum hover:text-plum-400 transition-colors"
            >
              Зарегистрироваться
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
