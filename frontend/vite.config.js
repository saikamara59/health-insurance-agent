import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Several backend routes share path prefixes with SPA routes (/clients, /compare, ...).
// Bypass the proxy for browser navigations (Accept: text/html) so Vite serves index.html
// and React Router handles the route. API calls (fetch/XHR) send Accept: application/json
// and fall through to the proxy as normal.
const bypassHtmlNavigations = (req) => {
  const accept = req.headers.accept || ''
  if (accept.includes('text/html')) return req.url
}

const proxyToBackend = {
  target: 'http://localhost:8000',
  changeOrigin: true,
  bypass: bypassHtmlNavigations,
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': proxyToBackend,
      '/clients': proxyToBackend,
      '/compare': proxyToBackend,
      '/calculate': proxyToBackend,
      '/translate': proxyToBackend,
      '/appeal': proxyToBackend,
      '/verify': proxyToBackend,
      '/estimate': proxyToBackend,
      '/plans': proxyToBackend,
      '/health': proxyToBackend,
      '/history': proxyToBackend,
      '/feedback': proxyToBackend,
      '/temporal': proxyToBackend,
      '/drugs': proxyToBackend,
      '/admin': proxyToBackend,
      '/__test': proxyToBackend,
    }
  }
})
