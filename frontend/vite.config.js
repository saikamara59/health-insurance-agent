import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/clients': 'http://localhost:8000',
      '/compare': 'http://localhost:8000',
      '/calculate': 'http://localhost:8000',
      '/translate': 'http://localhost:8000',
      '/appeal': 'http://localhost:8000',
      '/verify': 'http://localhost:8000',
      '/estimate': 'http://localhost:8000',
      '/plans': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
      '/feedback': 'http://localhost:8000',
      '/__test': 'http://localhost:8000',
    }
  }
})
