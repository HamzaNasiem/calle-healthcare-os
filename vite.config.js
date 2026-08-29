import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      // Local dev me /api/v1 ko backend pe forward karo (CORS issues avoid)
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/webhooks': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  build: {
    // Code splitting — har page alag chunk bane, initial load fast ho
    rollupOptions: {
      output: {
        manualChunks: {
          // React core
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          // Charts library (bhari hai — alag chunk)
          'charts': ['recharts'],
          // Icons library (bhari hai — alag chunk)
          'icons': ['lucide-react'],
          // API/utility
          'api': ['axios', 'date-fns'],
        }
      }
    },
    // Chunk size warning threshold
    chunkSizeWarningLimit: 600,
    // Source maps sirf development me
    sourcemap: false,
  }
});
