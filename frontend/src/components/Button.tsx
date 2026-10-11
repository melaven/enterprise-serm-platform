import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  children: React.ReactNode;
}

/**
 * Кнопка, соответствующая дизайн-системе Tenable SERM
 * Утилитарный flat-design без теней и скруглений
 */
export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  children,
  className = '',
  disabled,
  ...props
}) => {
  const baseClasses = `
    font-medium text-sm
    px-4 py-2
    border-2
    rounded-sm
    transition-colors duration-150
    disabled:opacity-50 disabled:cursor-not-allowed
    focus:outline-none focus:ring-2 focus:ring-plum focus:ring-offset-2 focus:ring-offset-ink
  `.trim().replace(/\s+/g, ' ');

  const variantClasses = {
    primary: `
      bg-plum hover:bg-plum-400 active:bg-plum-600
      text-white
      border-transparent
    `.trim().replace(/\s+/g, ' '),
    
    secondary: `
      bg-transparent hover:bg-ink-50
      text-chrome-300 hover:text-white
      border-chrome-600 hover:border-chrome-400
    `.trim().replace(/\s+/g, ' '),
    
    ghost: `
      bg-transparent hover:bg-plum-900/20
      text-chrome-400 hover:text-plum
      border-transparent
    `.trim().replace(/\s+/g, ' '),
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};
