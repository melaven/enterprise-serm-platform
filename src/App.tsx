import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { QuotaExceededHost } from '@/components/QuotaExceededHost';
import { Toaster } from '@/components/ui/sonner';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { ReviewsPage } from '@/pages/ReviewsPage';

// TODO: подставьте реальные реализации (API-клиент, auth-стор, хук квот).
declare function login(c: { email: string; password: string }): Promise<void>;
declare function register(d: { company: string; email: string; password: string }): Promise<void>;
declare function logout(): void;

export default function App() {
  return (
    <>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage onLogin={login} />} />
          <Route path="/register" element={<RegisterPage onRegister={register} />} />
          <Route
            element={
              <DashboardLayout title="Хиус" quota={null} online onLogout={logout} />
            }
          >
            <Route index element={null /* <AnalysisPanel … /> */} />
            <Route
              path="reviews"
              element={
                // TODO: reviews/total из вашего запроса списка; после сбора — refetch.
                <ReviewsPage />
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        {/* Глобальная модалка 402: ОБЯЗАТЕЛЬНО внутри Router (использует navigate) */}
        <QuotaExceededHost />
      </BrowserRouter>
      {/* Один раз на всё приложение, вне Routes */}
      <Toaster />
    </>
  );
}
