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
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

app.mount("#app")
