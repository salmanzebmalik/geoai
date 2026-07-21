import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    watch: {
      usePolling: true,
      interval: 400,
      ignored: ['**/node_modules/**', '**/dist/**', '**/../storage/**'],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8013',
        changeOrigin: true,
      },
      '/image-api': {
        target: 'http://127.0.0.1:8041',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/image-api/, ''),
      },
    },
  },
})
