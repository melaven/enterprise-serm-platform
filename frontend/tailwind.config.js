import colors from 'tailwindcss/colors';

const channelColor = (token) => `rgb(var(${token}) / <alpha-value>)`;

/**
 * Tenable SERM: enterprise flat. Plum is the branded surface; Lime is reserved for CTAs and small accents.
 *
 *   Ink     plum-tinted charcoal surfaces
 *   Chrome  accessible borders and secondary text
 *   Plum    #5A189A  branded surfaces and primary controls
 *   Lime    #C5FF4A  key CTAs and restrained accents
 *
 * Тени, ring и blur отключены на уровне corePlugins. Клавиатурный фокус
 * обозначается контрастным глобальным outline.
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
          DEFAULT: channelColor('--color-ink'),
          50: channelColor('--color-ink-50'),
          100: channelColor('--color-ink-100'),
          200: channelColor('--color-ink-200'),
          300: channelColor('--color-ink-300'),
          400: channelColor('--color-ink-400'),
          500: channelColor('--color-ink-500'),
          600: channelColor('--color-ink-600'),
          700: channelColor('--color-ink-700'),
          800: channelColor('--color-ink-800'),
          900: channelColor('--color-ink-900'),
          950: channelColor('--color-ink-950'),
        },
        zinc: colors.zinc,
        chrome: {
          DEFAULT: channelColor('--color-chrome'),
          50: channelColor('--color-chrome-50'),
          100: channelColor('--color-chrome-100'),
          200: channelColor('--color-chrome-200'),
          300: channelColor('--color-chrome-300'),
          400: channelColor('--color-chrome-400'),
          500: channelColor('--color-chrome-500'),
          600: channelColor('--color-chrome-600'),
          700: channelColor('--color-chrome-700'),
          800: channelColor('--color-chrome-800'),
          900: channelColor('--color-chrome-900'),
        },
        plum: {
          DEFAULT: channelColor('--color-plum'),
          50: channelColor('--color-plum-50'),
          100: channelColor('--color-plum-100'),
          200: channelColor('--color-plum-200'),
          300: channelColor('--color-plum-300'),
          400: channelColor('--color-plum-400'),
          500: channelColor('--color-plum-500'),
          600: channelColor('--color-plum-600'),
          700: channelColor('--color-plum-700'),
          800: channelColor('--color-plum-800'),
          900: channelColor('--color-plum-900'),
          deep: channelColor('--color-plum-deep'),
        },
        lime: {
          DEFAULT: channelColor('--color-lime'),
          50: channelColor('--color-lime-50'),
          100: channelColor('--color-lime-100'),
          200: channelColor('--color-lime-200'),
          300: channelColor('--color-lime-300'),
          400: channelColor('--color-lime-400'),
          500: channelColor('--color-lime-500'),
          600: channelColor('--color-lime-600'),
          700: channelColor('--color-lime-700'),
          800: channelColor('--color-lime-800'),
          900: channelColor('--color-lime-900'),
        },

        // Сохраняем старые токены для совместимости
        background: channelColor('--background'),
        foreground: channelColor('--foreground'),
        card: {
          DEFAULT: channelColor('--card'),
          foreground: channelColor('--card-foreground'),
        },
        popover: {
          DEFAULT: channelColor('--popover'),
          foreground: channelColor('--popover-foreground'),
        },
        primary: {
          DEFAULT: channelColor('--primary'),
          foreground: channelColor('--primary-foreground'),
        },
        secondary: {
          DEFAULT: channelColor('--secondary'),
          foreground: channelColor('--secondary-foreground'),
        },
        muted: {
          DEFAULT: channelColor('--muted'),
          foreground: channelColor('--muted-foreground'),
        },
        accent: {
          DEFAULT: channelColor('--accent'),
          foreground: channelColor('--accent-foreground'),
        },
        destructive: {
          DEFAULT: channelColor('--destructive'),
          foreground: channelColor('--destructive-foreground'),
        },
        border: channelColor('--border'),
        input: channelColor('--input'),
        ring: channelColor('--ring'),
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
    backdropFilter: false,
    backdropBlur: false,
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
