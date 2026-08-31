module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          bg: '#FAFAFA',
          card: '#FFFFFF',
          border: '#E5E7EB',
        },
        content: {
          primary: '#111827',
          secondary: '#6B7280',
        },
        brand: {
          50: '#EFF6FF',
          500: '#2563EB',
          600: '#1D4ED8',
        },
      },
      boxShadow: {
        flat: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        hover: '0 4px 12px -2px rgba(0, 0, 0, 0.08)',
      },
      borderRadius: {
        xl: '12px',
        '2xl': '16px',
      },
    },
  },
  plugins: [],
};

