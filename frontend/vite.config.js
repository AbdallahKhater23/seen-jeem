import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const projectRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(projectRoot, '..');
const adapterPath = path.resolve(repoRoot, 'backend/integration/frontendAdapter.js');

/** يخلي /admin يفتح لوحة الإدارة في التطوير مثل Nginx في الإنتاج. */
function adminRoutePlugin() {
  return {
    name: 'admin-route',
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        if (request.url === '/admin' || request.url === '/admin/') {
          request.url = '/admin.html';
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), adminRoutePlugin()],
  resolve: {
    alias: {
      '@trivia-adapter': adapterPath,
      '@shared': path.resolve(repoRoot, 'shared'),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    // المحوّل المشترك يعيش خارج جذر الواجهة، فنسمح لخادم التطوير بقراءته.
    fs: {
      allow: [repoRoot],
    },
    proxy: {
      '/api/v1': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(projectRoot, 'index.html'),
        admin: path.resolve(projectRoot, 'admin.html'),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    restoreMocks: true,
    setupFiles: ['./src/test/setup.js'],
  },
});
