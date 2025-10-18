/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      fontFamily: {
        'roboto': ['Roboto', 'sans-serif'],
        'sans': [
          'Roboto',
          // Windows
          'Segoe UI',
          // macOS
          '-apple-system',
          'BlinkMacSystemFont',
          'SF Pro Text',
          // Linux
          'Ubuntu',
          'Cantarell',
          'Noto Sans',
          'Liberation Sans',
          // Fallbacks
          'Arial',
          'sans-serif',
          // Emoji support
          'Apple Color Emoji',
          'Segoe UI Emoji',
          'Segoe UI Symbol',
          'Noto Color Emoji',
        ],
      },
      boxShadow: {
        'material': 'var(--md-elevation-1)',
        'material-2': 'var(--md-elevation-2)', 
        'material-4': 'var(--md-elevation-4)',
      }
    },
  },
  plugins: [],
}