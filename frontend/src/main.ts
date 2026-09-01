import { createApp } from "vue"
import { createPinia } from "pinia"
import ElementPlus from "element-plus"
import axios from "axios"
import { ElMessage } from "element-plus"
import "element-plus/dist/index.css"
import App from "./App.vue"
import router from "./router"
import "./styles/index.css"

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)

axios.defaults.baseURL = ""
const token = localStorage.getItem("smart-bi-token")
if (token) {
  axios.defaults.headers.common.Authorization = `Bearer ${token}`
}

// 局部 catch 与全局拦截器都可能对同一错误弹 toast，造成重复提示。
// 这里对“同一文案在短时间内”去重，确保一个错误最多弹一条；局部 catch
// 仍可显示更贴切的文案，拦截器只兜底未被局部处理的错误。
const recentErrorMessages = new Map<string, number>()
const ERROR_DEDUP_WINDOW_MS = 1500

function shouldShowErrorMessage(message: string): boolean {
  const now = Date.now()
  const lastShown = recentErrorMessages.get(message)
  if (lastShown !== undefined && now - lastShown < ERROR_DEDUP_WINDOW_MS) {
    return false
  }
  recentErrorMessages.set(message, now)
  // 避免无限增长
  if (recentErrorMessages.size > 50) {
    for (const [key, ts] of recentErrorMessages) {
      if (now - ts >= ERROR_DEDUP_WINDOW_MS) recentErrorMessages.delete(key)
    }
  }
  return true
}

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 未授权 - token 过期或无效，跳转登录页
    if (error?.response?.status === 401) {
      localStorage.removeItem("smart-bi-token")
      delete axios.defaults.headers.common.Authorization
      if (router.currentRoute.value.path !== "/login") {
        ElMessage.error("登录已过期，请重新登录")
        router.push("/login")
      }
      return Promise.reject(error)
    }
    const suppressGlobalError = Boolean((error?.config as any)?.suppressGlobalError)
    if (suppressGlobalError) return Promise.reject(error)
    const message =
      error?.response?.data?.detail || error?.message || "服务异常，请稍后重试"
    if (shouldShowErrorMessage(message)) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

// 兜底错误处理：避免某个组件在渲染/卸载/异步回调中抛错（如切换标签页时
// 第三方库在 DOM 生命周期边界上的 parentNode 报错）导致整个页面白屏。
// 业务逻辑仍应在局部 catch 并给出更具体的提示，这里只负责"不拖垮整页"。
app.config.errorHandler = (err, _instance, info) => {
  console.error("[Vue 渲染错误]", info, err)
}

window.addEventListener("unhandledrejection", (event) => {
  console.error("[未处理的 Promise 拒绝]", event.reason)
})

app.mount("#app")
