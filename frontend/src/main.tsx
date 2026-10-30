import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from './components/ui/sonner'
import { GlobalErrorBoundary } from './components/error/GlobalErrorBoundary'
import { QuotaExceededHost } from './features/dashboard/QuotaExceededHost'
import { RateLimitHost } from './features/dashboard/RateLimitHost'

// Локальные шрифты (@fontsource) - надёжнее чем Google Fonts CDN
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';

import App from './App.tsx'
import { LoginPage } from './pages/LoginPage.tsx'
import { RegisterPage } from './pages/RegisterPage.tsx'
import { BillingPage } from './pages/BillingPage.tsx'
import { LandingPage } from './pages/LandingPage.tsx'
import { ReviewsDashboard } from './features/reviews/ReviewsDashboard.tsx'
import { SettingsPage } from './pages/SettingsPage.tsx'
import { ProtectedRoute } from './features/auth/ProtectedRoute.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <GlobalErrorBoundary>
    <React.StrictMode>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/pricing" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          
          {/* Protected Routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <App />
              </ProtectedRoute>
            }
          />
          <Route
            path="/billing"
            element={
              <ProtectedRoute>
                <BillingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reviews"
            element={
              <ProtectedRoute>
                <ReviewsDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/*"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          
          {/* Catch all redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        
        {/* Toast Notifications - плоский дизайн без теней */}
        <Toaster />
        
        {/* Глобальная модалка для HTTP 402 Payment Required */}
        <QuotaExceededHost upgradePath="/billing" />
      </BrowserRouter>
      
      {/* Таймер 429 Rate Limit - вне Router, монтируется один раз */}
      <RateLimitHost />
    </React.StrictMode>
  </GlobalErrorBoundary>,
)
