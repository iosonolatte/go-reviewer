/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        go: {
          board: '#D2B48C',
          boardDark: '#C4A574',
          line: '#8B7355',
          black: '#1a1a1a',
          white: '#f5f5f5',
          wood: '#5D4037',
          woodLight: '#8D6E63',
          accent: '#FF6B35',
        }
      },
      fontFamily: {
        serif: ['"Noto Serif SC"', 'serif'],
        sans: ['"Noto Sans SC"', 'sans-serif'],
      },
      boxShadow: {
        'stone': '2px 2px 4px rgba(0,0,0,0.3)',
        'stone-hover': '3px 3px 6px rgba(0,0,0,0.4)',
      }
    },
  },
  plugins: [],
}
