/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        coral: {
          50: '#fff5f2',
          100: '#ffe8e0',
          200: '#ffd0c2',
          300: '#ffab94',
          400: '#ff7f5c',
          500: '#ff5a36',
          600: '#ed3a14',
          700: '#c62c0d',
          800: '#a42712',
          900: '#872616',
        },
        warm: {
          50: '#faf9f7',
          100: '#f3f1ed',
          200: '#e8e4dd',
          300: '#d5cfc4',
          400: '#b8af9f',
          500: '#9f9484',
          600: '#8a7e6f',
          700: '#73685c',
          800: '#61574e',
          900: '#524a43',
        },
      },
      fontFamily: {
        display: ['"Clash Display"', '"Satoshi"', 'system-ui', 'sans-serif'],
        body: ['"General Sans"', '"Satoshi"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
