import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppStore } from '@/store/useAppStore';

const loginSchema = z.object({
  email: z.string().min(1, 'Email обязателен').email('Некорректный email'),
  password: z.string().min(1, 'Пароль обязателен').min(6, 'Минимум 6 символов'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

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
  
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const [isLoading, setIsLoading] = useState(false);

  // Если уже залогинен, редирект на главную
  if (isAuthenticated) {
    navigate('/dashboard');
    return null;
  }

  const onSubmit = async (values: LoginFormValues) => {
    setIsLoading(true);
    
    try {
      const success = await performLogin(values.email, values.password);
      
      if (success) {
        toast.success('Вход выполнен', {
          description: `Добро пожаловать, ${values.email}`,
        });
        navigate('/dashboard');
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
          
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-chrome-300">
                Email
              </label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                disabled={isLoading}
                autoComplete="email"
                {...form.register('email')}
              />
              {form.formState.errors.email && (
                <p className="mt-1 text-sm text-plum">{form.formState.errors.email.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-medium text-chrome-300">
                Пароль
              </label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                disabled={isLoading}
                autoComplete="current-password"
                {...form.register('password')}
              />
              {form.formState.errors.password && (
                <p className="mt-1 text-sm text-plum">{form.formState.errors.password.message}</p>
              )}
            </div>

            <Button
              type="submit"
              variant="default"
              size="lg"
              disabled={isLoading}
              className="w-full bg-lime text-ink-950 hover:bg-lime/90"
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
