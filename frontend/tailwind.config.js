/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './admin.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Cairo', 'Readex Pro', 'Tajawal', 'system-ui', 'Segoe UI', 'sans-serif'],
      },
      colors: {
        brand: { 50: '#fff7ee', 100: '#ffead6', 200: '#ffd0a4', 300: '#ffb176', 400: '#ff943d', 500: '#f57928', 600: '#d35c16', 700: '#a74714', 800: '#883b1b', 900: '#6f301c' },
        cream: '#fffaf5',
        ink: {
          950: '#050713',
          900: '#090d1f',
          850: '#0d1228',
          800: '#111a36',
          700: '#1a2549',
          600: '#26345f',
        },
        neon: {
          cyan: '#22d3ee',
          blue: '#3b82f6',
          violet: '#a78bfa',
          pink: '#f472b6',
          amber: '#fbbf24',
          lime: '#a3e635',
        },
      },
      boxShadow: {
        glow: '0 0 24px rgba(34, 211, 238, 0.28)',
        'glow-violet': '0 0 28px rgba(167, 139, 250, 0.26)',
        panel: '0 12px 40px rgba(94, 46, 24, 0.07)',
      },
      backgroundImage: {
        'stage-radial':
          'radial-gradient(circle at 50% -10%, rgba(59,130,246,0.22), transparent 55%), radial-gradient(circle at 12% 100%, rgba(167,139,250,0.14), transparent 45%)',
      },
      keyframes: {
        pulseRing: {
          '0%': { transform: 'scale(0.85)', opacity: '0.9' },
          '70%': { transform: 'scale(1.35)', opacity: '0' },
          '100%': { transform: 'scale(1.35)', opacity: '0' },
        },
        strobe: {
          '0%, 100%': { opacity: '0.35' },
          '50%': { opacity: '1' },
        },
        floaty: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '200% 50%' },
          '100%': { backgroundPosition: '-200% 50%' },
        },
      },
      animation: {
        'pulse-ring': 'pulseRing 1.6s ease-out infinite',
        strobe: 'strobe 0.8s ease-in-out infinite',
        floaty: 'floaty 5s ease-in-out infinite',
        shimmer: 'shimmer 6s linear infinite',
      },
    },
  },
  plugins: [],
};
