import { ReactNode } from 'react';

/**
 * AuthShell - Обёртка для страниц авторизации
 * Строгая flat-обёртка для страниц авторизации
 */

interface AuthShellProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

export const AuthShell = ({ children, title, subtitle }: AuthShellProps) => {
  return (
    <div className="min-h-screen bg-ink flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 bg-plum rounded-none flex items-center justify-center relative overflow-hidden">
            <span className="text-white font-bold text-2xl relative z-10">TS</span>
          </div>
        </div>

        {/* Title & Subtitle */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-chrome-300 mb-2">
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm text-chrome-500">
              {subtitle}
            </p>
          )}
        </div>

        {/* Content Card */}
        <div className="card p-6">
          {children}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-chrome-500 mt-6">
          Tenable SERM © 2026 · Design System v1.0
        </p>
      </div>
    </div>
  );
};
