import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import App from './App.tsx'
import { LoginPage } from './pages/LoginPage.tsx'
import { ProtectedRoute } from './components/ProtectedRoute.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />
        
        {/* Protected Routes */}
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
      
      {/* Toast Notifications */}
      <Toaster 
        position="top-right" 
        richColors
        toastOptions={{
          style: {
            background: '#1A1A20',
            border: '1px solid #6B717D',
            color: '#C9CED6',
          },
        }}
      />
    </BrowserRouter>
  </React.StrictMode>,
)
