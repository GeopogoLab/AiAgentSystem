import defaultTheme from 'tailwindcss/defaultTheme';

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
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
      backgroundImage: {
        'grid-light': 'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
        'noise-light': 'radial-gradient(circle at 20% 20%, rgba(255,255,255,0.06), transparent 45%), radial-gradient(circle at 80% 0%, rgba(255,255,255,0.04), transparent 35%)',
      },
      boxShadow: {
        glow: '0 15px 40px rgba(0,0,0,0.45)',
        card: '0 25px 60px rgba(0,0,0,0.35)',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fade: {
          '0%': { opacity: 0, transform: 'translateY(8px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        pulseRing: {
          '0%': { boxShadow: '0 0 0 0 rgba(255,255,255,0.25)' },
          '70%': { boxShadow: '0 0 0 12px rgba(255,255,255,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(255,255,255,0)' },
        },
        ripple: {
          '0%': { transform: 'scale(0.95)', opacity: 0.7 },
          '100%': { transform: 'scale(1.15)', opacity: 0 },
        },
        voiceWave: {
          '0%, 100%': { transform: 'scaleY(0.4)' },
          '50%': { transform: 'scaleY(1)' },
        },
      },
      animation: {
        float: 'float 6s ease-in-out infinite',
        shimmer: 'shimmer 3s ease-in-out infinite',
        fade: 'fade 0.5s ease-out both',
        pulseRing: 'pulseRing 2.4s ease-out infinite',
        ripple: 'ripple 0.8s ease-out',
        voiceWave: 'voiceWave 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
