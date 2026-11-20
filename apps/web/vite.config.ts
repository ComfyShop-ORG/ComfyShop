import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '^/(api|downloads)(/|$)': { target: 'http://127.0.0.1:8688', changeOrigin: false } },
  },
});
