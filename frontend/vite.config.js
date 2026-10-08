import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Escuta em todas as interfaces (IPv4 e IPv6). No Windows, o padrão do Vite
    // pode ficar só em ::1 enquanto o navegador procura 127.0.0.1 — ou o inverso —
    // e o resultado é ERR_CONNECTION_REFUSED com o servidor aparentemente no ar.
    host: true,
    // Proxy elimina CORS em desenvolvimento: o front chama /api/... e o Vite
    // encaminha para o FastAPI, removendo o prefixo.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ''),
      },
    },
  },
})
