/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          900: '#134e4a',
        },
        dark: {
          bg: '#0b0f17',
          card: '#131b2e',
          border: '#24324f',
          surface: '#1c273e',
        }
      }
    },
  },
  plugins: [],
}
