/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#143b32',
        lime: '#d6ec63',
        paper: '#f4f1e8',
        clay: '#e97c55',
      },
      fontFamily: {
        display: ['Georgia', 'serif'],
        sans: ['Trebuchet MS', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
