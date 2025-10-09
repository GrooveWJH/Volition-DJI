/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      fontFamily: {
        'roboto': ['Roboto', 'sans-serif'],
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