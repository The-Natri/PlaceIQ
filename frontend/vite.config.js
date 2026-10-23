import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // During development (npm run dev) the page comes from Vite, so /api is
    // forwarded to the backend. The browser only ever talks to one origin,
    // exactly as in production, so no CORS is needed here either.
    proxy: {
      '/api': 'http://127.0.0.1:8080',
    },
  },
})
