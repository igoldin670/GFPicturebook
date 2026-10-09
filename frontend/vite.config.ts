import { defineConfig } from 'vite';
export default defineConfig({
  build: { assetsDir: 'static/assets' },
  server: { proxy: { '/api': 'http://127.0.0.1:8000', '/admin': 'http://127.0.0.1:8000', '/static': 'http://127.0.0.1:8000' } }
});
