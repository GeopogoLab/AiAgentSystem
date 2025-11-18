import defaultTheme from 'tailwindcss/defaultTheme';

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Space Grotesk', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        ink: {
          50: '#f9f9f9',
          100: '#f2f2f2',
          200: '#e5e5e5',
          300: '#d4d4d4',
          400: '#a3a3a3',
          500: '#737373',
          600: '#525252',
          700: '#404040',
          800: '#262626',
          900: '#171717',
          950: '#050505',
        },
      },
      boxShadow: {
        glow: '0 25px 60px rgba(0,0,0,0.45)',
      },
      keyframes: {
        slideUp: {
          '0%': { opacity: 0, transform: 'translateY(16px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        pulseBar: {
          '0%, 100%': { transform: 'scaleY(0.7)' },
          '50%': { transform: 'scaleY(1)' },
        },
      },
      animation: {
        slideUp: 'slideUp 0.5s ease-out both',
        pulseBar: 'pulseBar 1.2s ease-in-out infinite',
      },
      backgroundImage: {
        'grid-light': 'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
};
