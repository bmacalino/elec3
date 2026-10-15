import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Flask serves the API; `npm run dev` forwards /api to it. Keep the port
    // the same as PORT in run.py.
    proxy: {
      '/api': 'http://127.0.0.1:5050',
    },
  },
})
