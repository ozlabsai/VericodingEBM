/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0d1117',
        panel: '#161b22',
        border: '#30363d',
        accent: '#2c5fc7',
        warm: '#cc4040',
      },
    },
  },
  plugins: [],
}
