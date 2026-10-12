import colors from 'tailwindcss/colors';

/**
 * Tenable SERM: монолитный flat. Только Ink / Zinc (Chrome) / Royal Plum / Electric Lime.
 *
 *   Ink     #000000 (фон приложения), zinc-950 (карточки)
 *   Chrome  zinc-800 (рамки), zinc-400 (второстепенный текст)
 *   Plum    #5A189A  основные кнопки, активные пункты меню, логотип
 *   Lime    #C5FF4A  позитивные метрики, успешные статусы, прогресс квот, онлайн-индикаторы
 *
 * Тени, кольца, градиенты и filter-blur ОТКЛЮЧЕНЫ на уровне corePlugins:
 * классы shadow-*, ring-*, bg-gradient-*, blur-* просто не генерируются
 * (в том числе внутри shadcn/ui: фокус рисует глобальный outline, см. globals.css).
 *
 * Матовое стекло (backdrop-filter + backdrop-blur-*) ВКЛЮЧЕНО осознанно: фирменный
 * приём ХИУС для оверлеев модалок (bg-black/60 backdrop-blur-md). Остальные backdrop-*
 * (brightness, contrast, ...) отключены: цвет и свечение через стекло не добавляем.
 *
 * Токены shadcn (background, card, primary...) сохранены и привязаны к палитре,
 * поэтому штатные компоненты shadcn/ui продолжают работать.
 */

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],

  theme: {
    // Полная замена палитры: цветов вне системы (red-500, blue-600...) нет.
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      black: '#000000',
      white: '#FFFFFF',
      zinc: colors.zinc,
      plum: { DEFAULT: '#5A189A', deep: '#43127A' },
      lime: '#C5FF4A',
      // Единственный «красный» системы: критичные отзывы, ошибки. Читаем на Ink (~6.5:1).
      danger: '#FF5C5C',

      // shadcn/ui
      background: '#000000',
      foreground: '#FAFAFA',
      card: { DEFAULT: '#09090B', foreground: '#FAFAFA' },
      popover: { DEFAULT: '#09090B', foreground: '#FAFAFA' },
      primary: { DEFAULT: '#5A189A', foreground: '#FFFFFF' },
      secondary: { DEFAULT: '#18181B', foreground: '#FAFAFA' },
      muted: { DEFAULT: '#18181B', foreground: '#A1A1AA' },
      accent: { DEFAULT: '#C5FF4A', foreground: '#000000' },
      // красного в системе нет: деструктивное действие = plum + белый текст
      destructive: { DEFAULT: '#5A189A', foreground: '#FFFFFF' },
      border: '#27272A',
      input: '#27272A',
      ring: '#C5FF4A',
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
