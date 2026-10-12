import { useId, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { AUTH_LABEL, AUTH_LINK, AuthShell } from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export interface RegisterPageProps {
  onRegister: (data: { company: string; email: string; password: string }) => Promise<void>;
}

const MIN_PASSWORD = 8;

export function RegisterPage({ onRegister }: RegisterPageProps) {
  const uid = useId();
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [pending, setPending] = useState(false);

  const mismatch = confirm.length > 0 && confirm !== password;
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    if (password.length < MIN_PASSWORD) {
      toast.error(`Пароль: минимум ${MIN_PASSWORD} символов`);
      return;
    }
    if (password !== confirm) {
      toast.error('Пароли не совпадают');
      return;
    }
    setPending(true);
    try {
      await onRegister({ company: company.trim(), email: email.trim(), password });
      toast.success('Аккаунт создан');
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : 'Не удалось зарегистрироваться');
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      title="Регистрация"
      footer={
        <>
          Уже есть аккаунт?{' '}
          <Link to="/login" className={AUTH_LINK}>
            Войти
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <label htmlFor={`${uid}-company`} className={AUTH_LABEL}>
            Компания
          </label>
          <Input
            id={`${uid}-company`}
            name="company"
            autoComplete="organization"
            required
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            disabled={pending}
          />
        </div>
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
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            aria-invalid={tooShort}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={pending}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor={`${uid}-confirm`} className={AUTH_LABEL}>
            Повторите пароль
          </label>
          <Input
            id={`${uid}-confirm`}
            type="password"
            name="confirm"
            autoComplete="new-password"
            required
            aria-invalid={mismatch}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={pending}
          />
        </div>
        <Button type="submit" size="lg" className="w-full" disabled={pending}>
          {pending ? 'Создание…' : 'Создать аккаунт'}
        </Button>
      </form>
    </AuthShell>
  );
}
