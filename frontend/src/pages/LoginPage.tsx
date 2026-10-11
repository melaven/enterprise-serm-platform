import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import apiClient from '../api/client';
import { useAuth } from '../store/useAppStore';
import { Button } from '../components/ui/button';

/**
 * Страница авторизации
 * Строгий flat-design, центрированная форма на фоне Ink
 */
export const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if (!email || !password) {
      toast.error('Заполните все поля');
      return;
    }

    try {
      setLoading(true);
      
      // FormData для OAuth2PasswordRequestForm
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await apiClient.post('/api/v1/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token, token_type } = response.data;
      
      // Получаем данные пользователя
      const userResponse = await apiClient.get('/api/v1/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      // Сохраняем в Zustand (токен автоматически попадёт в localStorage через persist)
      login(access_token, userResponse.data);

      // Устанавливаем токен в API клиент
      localStorage.setItem('auth_token', access_token);

      toast.success('Успешный вход!');
      navigate('/');
    } catch (error: any) {
      console.error('Login failed:', error);
      
      if (error.response?.status === 401) {
        toast.error('Неверный email или пароль');
      } else if (error.response?.status === 403) {
        toast.error('Доступ запрещён');
      } else {
        toast.error('Ошибка при входе. Попробуйте позже.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink flex items-center justify-center p-4">
      {/* Login Card */}
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 bg-plum rounded-none flex items-center justify-center">
            <span className="text-white font-bold text-2xl">TS</span>
          </div>
        </div>

        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-chrome-300 mb-2">
            Tenable SERM
          </h1>
          <p className="text-sm text-chrome-500">
            Вход в систему
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="card p-6 space-y-6">
          {/* Email Field */}
          <div>
            <label htmlFor="email" className="text-label mb-2 block">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              placeholder="user@example.com"
              disabled={loading}
              autoComplete="email"
              autoFocus
            />
          </div>

          {/* Password Field */}
          <div>
            <label htmlFor="password" className="text-label mb-2 block">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              placeholder="••••••••"
              disabled={loading}
              autoComplete="current-password"
            />
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            className="w-full"
            disabled={loading}
          >
            {loading ? 'Вход...' : 'Войти'}
          </Button>
        </form>

        {/* Footer */}
        <p className="text-center text-xs text-chrome-500 mt-6">
          Tenable SERM © 2026 · Design System v1.0
        </p>
      </div>
    </div>
  );
};
