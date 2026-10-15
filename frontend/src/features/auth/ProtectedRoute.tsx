import { Navigate } from 'react-router-dom';
import { useAuth } from '../../store/useAppStore';

/**
 * Защищённый роут
 * Редиректит на /login если пользователь не авторизован
 */
interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, token } = useAuth();

  // Проверяем наличие токена в Zustand store
  if (!isAuthenticated || !token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};
