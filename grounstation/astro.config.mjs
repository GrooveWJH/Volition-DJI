import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import node from '@astrojs/node';

export default defineConfig({
  output: 'server',
  adapter: node({
    mode: 'standalone'
  }),
  server: {
    port: 4321,
    host: true
  },
  integrations: [tailwind()],
  vite: {
    build: {
      // 禁用缓存，强制重新构建
      sourcemap: true,
    },
    server: {
      // 禁用客户端缓存
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      }
    },
    optimizeDeps: {
      include: ['mqtt'],
      force: true
    },
    define: {
      global: 'globalThis',
    }
  }
});