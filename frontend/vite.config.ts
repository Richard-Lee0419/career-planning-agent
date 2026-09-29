import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backend = env.VITE_API_PROXY_TARGET || env.VITE_API_BASE_URL || 'http://localhost:8000';

  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            const path = id.replace(/\\/g, '/');
            if (path.includes('/node_modules/zrender/')) return 'zrender';
            if (path.includes('/node_modules/echarts/')) return 'echarts';
            if (/\/node_modules\/(react|react-dom|scheduler)\//.test(path)) return 'react-vendor';
            if (/\/node_modules\/(react-router|react-router-dom|@remix-run\/router)\//.test(path)) return 'router-vendor';
            if (path.includes('/node_modules/@ant-design/') || path.includes('/node_modules/@rc-component/') || /\/node_modules\/rc-[^/]+\//.test(path)) return 'antd-foundation';
          }
        }
      }
    },
    server: {
      port: 5173,
      proxy: {
        '/api': backend,
        '/static': backend
      }
    }
  };
});
