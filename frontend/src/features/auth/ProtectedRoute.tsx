import { Navigate, useLocation } from 'react-router-dom';
import { useAuth, useAppStore } from '../../store/useAppStore';
import { useEffect, useState } from 'react';
import { tokens } from '@/api/services';

/**
 * Защищённый роут
 * Редиректит на /login если пользователь не авторизован
 * Сохраняет return_url для редиректа после успешного логина
 * Ждёт гидратации Zustand persist перед проверкой авторизации
 */
interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, token } = useAuth();
  const [hydrated, setHydrated] = useState(useAppStore.persist.hasHydrated());
  const hasValidToken = token !== null && tokens.get() === token;
  const location = useLocation();

  useEffect(() => {
    // Wait for Zustand persist hydration
    const unsubFinishHydration = useAppStore.persist.onFinishHydration(() => {
      setHydrated(true);
    });

    return () => {
      unsubFinishHydration();
    };
  }, []);

  // Show loading while hydrating
  if (!hydrated) {
    return null; // or <div>Loading...</div>
  }

  // Check auth after hydration
  if (!isAuthenticated || !hasValidToken) {
    return <Navigate to="/login" state={{ return_url: location.pathname }} replace />;
  }

  return <>{children}</>;
};
