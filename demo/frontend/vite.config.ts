import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Default to absolute `/` so client-side routes like /landscape and
// /landscape3d resolve their JS/CSS bundles correctly. Set VITE_BASE to a
// fixed subpath (e.g. `/VericodingEBM/`) when deploying under a non-root URL
// such as GitHub Pages with a project page.
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8765', changeOrigin: true },
    },
  },
})
