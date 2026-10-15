import colors from 'tailwindcss/colors';

/**
 * Tenable SERM: монолитный flat. Только Ink / Zinc (Chrome) / Royal Plum / Electric Lime.
 *
 *   Ink     #000000 (фон приложения), zinc-950 (карточки)
 *   Chrome  zinc-800 (рамки), zinc-400 (второстепенный текст)
 *   Plum    #5A189A  основные кнопки, активные пункты меню, логотип
 *   Lime    #C5FF4A  позитивные метрики, успешные статусы, прогресс квот, онлайн-индикаторы
 *
 * Тени, кольца, градиенты, blur и стекло ОТКЛЮЧЕНЫ на уровне corePlugins:
 * классы shadow-*, ring-*, bg-gradient-*, backdrop-blur-* просто не генерируются
 * (в том числе внутри shadcn/ui: фокус рисует глобальный outline, см. globals.css).
 *
 * Токены shadcn (background, card, primary...) сохранены и привязаны к палитре,
 * поэтому штатные компоненты shadcn/ui продолжают работать.
 */

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],

  theme: {
    extend: {
      // Расширенная палитра через CSS переменные
      colors: {
        transparent: 'transparent',
        current: 'currentColor',
        black: '#000000',
        white: '#FFFFFF',
        ink: {
          DEFAULT: 'var(--color-ink)',
          50: 'var(--color-ink-50)',
          100: 'var(--color-ink-100)',
          200: 'var(--color-ink-200)',
          300: 'var(--color-ink-300)',
          400: 'var(--color-ink-400)',
          500: 'var(--color-ink-500)',
          600: 'var(--color-ink-600)',
          700: 'var(--color-ink-700)',
          800: 'var(--color-ink-800)',
          900: 'var(--color-ink-900)',
          950: 'var(--color-ink-950)',
        },
        zinc: colors.zinc,
        chrome: {
          DEFAULT: 'var(--color-chrome)',
          50: 'var(--color-chrome-50)',
          100: 'var(--color-chrome-100)',
          200: 'var(--color-chrome-200)',
          300: 'var(--color-chrome-300)',
          400: 'var(--color-chrome-400)',
          500: 'var(--color-chrome-500)',
          600: 'var(--color-chrome-600)',
          700: 'var(--color-chrome-700)',
          800: 'var(--color-chrome-800)',
          900: 'var(--color-chrome-900)',
        },
        plum: {
          DEFAULT: 'var(--color-plum)',
          50: 'var(--color-plum-50)',
          100: 'var(--color-plum-100)',
          200: 'var(--color-plum-200)',
          300: 'var(--color-plum-300)',
          400: 'var(--color-plum-400)',
          500: 'var(--color-plum-500)',
          600: 'var(--color-plum-600)',
          700: 'var(--color-plum-700)',
          800: 'var(--color-plum-800)',
          900: 'var(--color-plum-900)',
          deep: 'var(--color-plum-deep)',
        },
        lime: {
          DEFAULT: 'var(--color-lime)',
          50: 'var(--color-lime-50)',
          100: 'var(--color-lime-100)',
          200: 'var(--color-lime-200)',
          300: 'var(--color-lime-300)',
          400: 'var(--color-lime-400)',
          500: 'var(--color-lime-500)',
          600: 'var(--color-lime-600)',
          700: 'var(--color-lime-700)',
          800: 'var(--color-lime-800)',
          900: 'var(--color-lime-900)',
        },

        // Сохраняем старые токены для совместимости
        background: 'var(--color-background)',
        foreground: 'var(--color-foreground)',
        card: {
          DEFAULT: 'var(--color-card)',
          foreground: 'var(--color-card-foreground)',
        },
        popover: {
          DEFAULT: 'var(--color-popover)',
          foreground: 'var(--color-popover-foreground)',
        },
        primary: {
          DEFAULT: 'var(--color-primary)',
          foreground: 'var(--color-primary-foreground)',
        },
        secondary: {
          DEFAULT: 'var(--color-secondary)',
          foreground: 'var(--color-secondary-foreground)',
        },
        muted: {
          DEFAULT: 'var(--color-muted)',
          foreground: 'var(--color-muted-foreground)',
        },
        accent: {
          DEFAULT: 'var(--color-accent)',
          foreground: 'var(--color-accent-foreground)',
        },
        destructive: {
          DEFAULT: 'var(--color-destructive)',
          foreground: 'var(--color-destructive-foreground)',
        },
        border: 'var(--color-border)',
        input: 'var(--color-input)',
        ring: 'var(--color-ring)',
      },

      // Максимум 2px везде, включая rounded-full и shadcn (rounded-lg/md/sm).
      borderRadius: {
        none: '0',
        sm: '2px',
        DEFAULT: '2px',
        md: '2px',
        lg: '2px',
        xl: '2px',
        '2xl': '2px',
        '3xl': '2px',
        full: '2px',
      },
      boxShadow: { none: 'none' },
      dropShadow: {},

      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'Arial', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },

  corePlugins: {
    boxShadow: false,
    boxShadowColor: false,
    ringWidth: false,
    ringColor: false,
    ringOffsetWidth: false,
    ringOffsetColor: false,
    ringOpacity: false,
    dropShadow: false,
    blur: false,
    backdropFilter: true,  // Включаем для QuotaExceededDialog overlay
    backdropBlur: true,    // Включаем для матового стекла (bg-black/60 + backdrop-blur-md)
    backdropBrightness: false,
    backdropContrast: false,
    backdropGrayscale: false,
    backdropHueRotate: false,
    backdropInvert: false,
    backdropOpacity: false,
    backdropSaturate: false,
    backdropSepia: false,
    backgroundImage: false,
    gradientColorStops: false,
  },
  plugins: [],
};
