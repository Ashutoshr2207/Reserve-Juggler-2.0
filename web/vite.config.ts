import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure(proxy) {
          // Preserve the backend's same-origin check through this local dev proxy.
          proxy.on('proxyReq', (outgoing, incoming) => {
            if (incoming.headers.origin === `http://${incoming.headers.host}`) {
              outgoing.setHeader('Origin', 'http://127.0.0.1:8000');
            }
          });
        }
      }
    }
  }
});
