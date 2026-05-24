import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `base: './'` makes the built site portable: it works whether served from
// `/` (GitHub Pages root), `/demo/` (subpath), or opened via file:// for local
// review. Set VITE_BASE if you need a fixed absolute base.
export default defineConfig({
  base: process.env.VITE_BASE ?? './',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8765', changeOrigin: true },
    },
  },
})
