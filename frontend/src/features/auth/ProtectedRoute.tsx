import { Navigate } from 'react-router-dom';
import { useAuth, useAppStore } from '../../store/useAppStore';
import { useEffect, useState } from 'react';
import { tokens } from '@/api/services';

/**
 * Защищённый роут
 * Редиректит на /login если пользователь не авторизован
 * Ждёт гидратации Zustand persist перед проверкой авторизации
 */
interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, token } = useAuth();
  const [hydrated, setHydrated] = useState(useAppStore.persist.hasHydrated());
  const hasValidToken = token !== null && tokens.get() === token;

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
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};
