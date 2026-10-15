import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: true, // Allow external access (e.g., from mobile)
    strictPort: false, // Use next available port if 3000 is busy
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        // Handle WebSocket upgrades if needed
        ws: true,
      },
    },
  },
  build: {
    // Отключаем source maps для продакшна (безопасность + размер)
    sourcemap: false,
    
    // Увеличиваем chunk size warning порог (наши vendor-чанки большие, это OK)
    chunkSizeWarningLimit: 1000,
    
    // Оптимизация минификации
    minify: 'esbuild',
    
    rollupOptions: {
      output: {
        // Manual chunk splitting для оптимального кэширования
        manualChunks: (id) => {
          // Vendor chunk: React ecosystem
          if (id.includes('node_modules/react') || 
              id.includes('node_modules/react-dom') ||
              id.includes('node_modules/react-router-dom') ||
              id.includes('node_modules/scheduler')) {
            return 'vendor-react';
          }
          
          // UI Libraries: Radix UI + Lucide icons
          if (id.includes('node_modules/@radix-ui') ||
              id.includes('node_modules/lucide-react')) {
            return 'vendor-ui';
          }
          
          // State Management: Zustand
          if (id.includes('node_modules/zustand')) {
            return 'vendor-state';
          }
          
          // HTTP Client: Axios
          if (id.includes('node_modules/axios')) {
            return 'vendor-http';
          }
          
          // Остальные node_modules в общий vendor
          if (id.includes('node_modules')) {
            return 'vendor-misc';
          }
        },
        
        // Naming pattern для chunks (cache busting)
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
    
    // Target современных браузеров для меньшего размера
    target: 'es2020',
  },
  
  esbuild: {
    // Удаляем console.log и debugger в продакшне
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
  },
})
