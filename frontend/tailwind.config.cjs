/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Базовая палитра B2B SaaS Dashboard
        ink: {
          DEFAULT: '#0B0B0F',
          50: '#1A1A20',
          100: '#0B0B0F',
        },
        chrome: {
          DEFAULT: '#C9CED6',
          50: '#F5F6F7',
          100: '#E8EAED',
          200: '#D4D8DE',
          300: '#C9CED6',
          400: '#A8AEB8',
          500: '#888E9A',
          600: '#6B717D',
        },
        plum: {
          DEFAULT: '#5A189A',
          50: '#E8D6F5',
          100: '#D1ADEB',
          200: '#B984E0',
          300: '#9C5BC9',
          400: '#7B36B3',
          500: '#5A189A',
          600: '#4B1380',
          700: '#3C0F66',
          800: '#2D0B4D',
          900: '#1E0733',
        },
        lime: {
          DEFAULT: '#C5FF4A',
          50: '#F7FFE5',
          100: '#EFFFCC',
          200: '#E7FFB3',
          300: '#DFFF99',
          400: '#D7FF80',
          500: '#C5FF4A',
          600: '#B3F032',
          700: '#9CD91A',
          800: '#7AB315',
          900: '#5A8510',
        },
        // shadcn/ui переменные (адаптированы под нашу палитру)
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      // ЖЕСТКО отключаем все тени
      boxShadow: {
        none: 'none',
        DEFAULT: 'none',
        sm: 'none',
        md: 'none',
        lg: 'none',
        xl: 'none',
        '2xl': 'none',
        inner: 'none',
      },
      // Ограничиваем скругление до 2px максимум
      borderRadius: {
        none: '0',
        sm: '2px',
        DEFAULT: '2px',
        md: '2px',
        lg: '2px',
        xl: '2px',
        '2xl': '2px',
        '3xl': '2px',
        full: '9999px', // оставляем только для круглых элементов
      },
      // Запрещаем backdrop-blur
      backdropBlur: {
        none: '0',
        DEFAULT: '0',
        sm: '0',
        md: '0',
        lg: '0',
        xl: '0',
        '2xl': '0',
        '3xl': '0',
      },
      // Типографика для B2B интерфейсов
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      fontSize: {
        'xs': ['11px', { lineHeight: '16px', letterSpacing: '0.01em' }],
        'sm': ['13px', { lineHeight: '20px', letterSpacing: '0' }],
        'base': ['14px', { lineHeight: '22px', letterSpacing: '0' }],
        'lg': ['16px', { lineHeight: '24px', letterSpacing: '-0.01em' }],
        'xl': ['20px', { lineHeight: '28px', letterSpacing: '-0.02em' }],
        '2xl': ['24px', { lineHeight: '32px', letterSpacing: '-0.02em' }],
        '3xl': ['32px', { lineHeight: '40px', letterSpacing: '-0.03em' }],
      },
      // Spacing для утилитарного дизайна
      spacing: {
        '0.5': '2px',
        '1': '4px',
        '1.5': '6px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '5': '20px',
        '6': '24px',
        '8': '32px',
        '10': '40px',
        '12': '48px',
        '16': '64px',
        '20': '80px',
        '24': '96px',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
  // СТРОГИЙ режим: запрещаем любые тени и blur на уровне конфига
  corePlugins: {
    backdropBlur: false,
  },
}
