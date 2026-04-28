import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import path from "node:path"

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8001"

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
      "/api": apiProxyTarget
    }
  }
})
