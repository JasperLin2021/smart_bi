import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import path from "node:path"

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8001"
const agentProxyTarget = process.env.VITE_AGENT_PROXY_TARGET || "http://localhost:8010"

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src")
    }
  },
  server: {
    port: 16057,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        xfwd: true
      },
      "/agent-api": {
        target: agentProxyTarget,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/agent-api/, "")
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts"],
          "element-plus": ["element-plus"],
          xlsx: ["xlsx"]
        }
      }
    }
  }
})
