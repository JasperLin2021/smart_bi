import { defineStore } from "pinia"
import axios from "axios"
import { ElMessage } from "element-plus"

export interface UserProfile {
  id: number
  username: string
  role: 'user' | 'org_admin' | 'super_admin'
  org_id: number | null
  org_name: string | null
}

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("smart-bi-token") || "",
    profile: null as UserProfile | null
  }),
  getters: {
    isOrgAdmin(): boolean {
      return this.profile?.role === 'org_admin' || this.profile?.role === 'super_admin'
    },
    isSuperAdmin(): boolean {
      return this.profile?.role === 'super_admin'
    }
  },
  actions: {
    async login(username: string, password: string) {
      try {
        const response = await axios.post("/api/auth/login", {
          username,
          password
        })
        this.token = response.data.access_token
        localStorage.setItem("smart-bi-token", this.token)
        axios.defaults.headers.common.Authorization = `Bearer ${this.token}`
        await this.fetchProfile()
      } catch (error) {
        ElMessage.error("登录失败，请检查账号或密码")
        throw error
      }
    },
    async fetchProfile() {
      const response = await axios.get("/api/auth/me")
      this.profile = response.data
    },
    logout() {
      this.token = ""
      this.profile = null
      localStorage.removeItem("smart-bi-token")
      delete axios.defaults.headers.common.Authorization
    }
  }
})
