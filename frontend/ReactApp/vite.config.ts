import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/login': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/logout': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/session_request': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/session_post': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/cat_request': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/question_post': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/question_submit': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/grade_question': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/ping': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/api': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/admin': process.env.BACKEND_URL ?? 'http://localhost:5000',
      '/stats': process.env.BACKEND_URL ?? 'http://localhost:5000',
    },
  },
})
