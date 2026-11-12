import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev 代理：把 /api、/reports 转发到 Flask 后端（python web.py，默认 5000）
// 构建产物输出到 frontend/dist，由后端 Flask 托管
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/reports': 'http://127.0.0.1:5000'
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})
