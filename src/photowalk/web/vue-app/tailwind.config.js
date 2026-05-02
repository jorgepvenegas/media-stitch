/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {
      colors: {
        'app-bg': '#1a1a2e',
        'panel': '#16213e',
        'surface': '#0f0f1a',
        'video-bar': '#4a90d9',
        'image-bar': '#5cb85c',
        'accent': '#d9a04a',
        'error': '#e74c3c',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
}
