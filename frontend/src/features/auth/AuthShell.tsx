import { ReactNode, useState } from 'react';

/**
 * AuthShell - Обёртка для страниц авторизации
 * Строгий flat-design с минималистичным блестящим эффектом на кнопках
 */

interface AuthShellProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

export const AuthShell = ({ children, title, subtitle }: AuthShellProps) => {
  const [glareTriggered, setGlareTriggered] = useState(false);

  const handleGlare = () => {
    setGlareTriggered(true);
    setTimeout(() => setGlareTriggered(false), 800);
  };

  return (
    <div className="min-h-screen bg-ink flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 bg-plum rounded-none flex items-center justify-center relative overflow-hidden">
            <span className="text-white font-bold text-2xl relative z-10">TS</span>
            {/* Резкий блик при ховере */}
            <div
              className={`absolute inset-0 w-1/3 h-full bg-gradient-to-r from-transparent via-white/40 to-transparent ${
                glareTriggered ? 'animate-hard-glare' : ''
              }`}
              style={{ left: '-150%' }}
            />
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
        <div 
          className="card p-6"
          onMouseEnter={handleGlare}
        >
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
