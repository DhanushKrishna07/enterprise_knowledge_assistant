import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    proxy: {
      '/ask': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/ingest': 'http://localhost:8000',
      '/feedback': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/sources': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/ready': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
