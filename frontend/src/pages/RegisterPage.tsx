import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../store/useAppStore';
import { Button } from '../components/ui/button';
import { AuthShell } from '../components/AuthShell';

/**
 * Страница регистрации
 * Использует centralized API через Zustand store
 */
export const RegisterPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { performRegister } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    // Валидация
    if (!email || !password || !confirmPassword) {
      toast.error('Заполните все поля');
      return;
    }

    if (password !== confirmPassword) {
      toast.error('Пароли не совпадают');
      return;
    }

    if (password.length < 6) {
      toast.error('Пароль должен быть не менее 6 символов');
      return;
    }

    setLoading(true);
    const success = await performRegister(email, password);
    setLoading(false);

    if (success) {
      toast.success('Регистрация успешна! Вы автоматически вошли в систему');
      navigate('/');
    }
  };

  return (
    <AuthShell 
      title="Создать аккаунт" 
      subtitle="Регистрация в Tenable SERM"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
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
            placeholder="Минимум 6 символов"
            disabled={loading}
            autoComplete="new-password"
          />
        </div>

        {/* Confirm Password Field */}
        <div>
          <label htmlFor="confirmPassword" className="text-label mb-2 block">
            Подтвердите пароль
          </label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="input-field"
            placeholder="••••••••"
            disabled={loading}
            autoComplete="new-password"
          />
        </div>

        {/* Submit Button */}
        <Button
          type="submit"
          className="w-full"
          disabled={loading}
        >
          {loading ? 'Регистрация...' : 'Зарегистрироваться'}
        </Button>

        {/* Link to Login */}
        <div className="text-center text-sm text-chrome-500">
          Уже есть аккаунт?{' '}
          <button
            type="button"
            onClick={() => navigate('/login')}
            className="text-plum hover:text-plum/80 font-medium transition-colors"
            disabled={loading}
          >
            Войти
          </button>
        </div>
      </form>
    </AuthShell>
  );
};
