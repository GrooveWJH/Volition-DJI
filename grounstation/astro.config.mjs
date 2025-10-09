import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  output: 'static',
  server: {
    port: 4321,
    host: true
  },
  integrations: [tailwind()]
});