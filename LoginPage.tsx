import { useId, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { AUTH_LABEL, AUTH_LINK, AuthShell } from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export interface LoginPageProps {
  /** Должен бросить Error с человекочитаемым message при отказе */
  onLogin: (credentials: { email: string; password: string }) => Promise<void>;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const uid = useId();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    setPending(true);
    try {
      await onLogin({ email: email.trim(), password });
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : 'Не удалось войти');
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      title="Вход в систему"
      footer={
        <>
          Нет аккаунта?{' '}
          <Link to="/register" className={AUTH_LINK}>
            Регистрация
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-6" noValidate={false}>
        <div className="space-y-2">
          <label htmlFor={`${uid}-email`} className={AUTH_LABEL}>
            Email
          </label>
          <Input
            id={`${uid}-email`}
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={pending}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor={`${uid}-password`} className={AUTH_LABEL}>
            Пароль
          </label>
          <Input
            id={`${uid}-password`}
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={pending}
          />
        </div>
        <Button type="submit" size="lg" className="w-full" disabled={pending}>
          {pending ? 'Вход…' : 'Войти'}
        </Button>
      </form>
    </AuthShell>
  );
}
