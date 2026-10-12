import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from './components/ui/sonner'
import { QuotaExceededHost } from './components/QuotaExceededHost'

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
import { ReviewsPage } from './pages/ReviewsPage.tsx'
import { ProtectedRoute } from './components/ProtectedRoute.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        
        {/* Protected Routes */}
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
              <ReviewsPage />
            </ProtectedRoute>
          }
        />
        <Route 
          path="/" 
          element={
            <ProtectedRoute>
              <App />
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
  </React.StrictMode>,
)
