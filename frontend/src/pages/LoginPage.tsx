import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../store/useAppStore';
import { Button } from '../components/ui/button';
import { AuthShell } from '../components/AuthShell';

/**
 * Страница авторизации
 * Использует centralized API через Zustand store
 */
export const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { performLogin } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if (!email || !password) {
      toast.error('Заполните все поля');
      return;
    }

    setLoading(true);
    const success = await performLogin(email, password);
    setLoading(false);

    if (success) {
      toast.success('Успешный вход!');
      navigate('/');
    }
  };

  return (
    <AuthShell 
      title="Tenable SERM" 
      subtitle="Вход в систему"
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

        {/* Link to Register */}
        <div className="text-center text-sm text-chrome-500">
          Нет аккаунта?{' '}
          <button
            type="button"
            onClick={() => navigate('/register')}
            className="text-plum hover:text-plum/80 font-medium transition-colors"
            disabled={loading}
          >
            Зарегистрироваться
          </button>
        </div>
      </form>
    </AuthShell>
  );
};
