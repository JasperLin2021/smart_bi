<template>
  <div class="app-root">
    <router-view v-if="isStandalone" />
    <MainLayout v-else />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import MainLayout from "@/layouts/MainLayout.vue"

const route = useRoute()
// 登录页与公开页（embed/分享页）独立全屏渲染，不套主框架的鉴权 UI
const isStandalone = computed(() => route.path === "/login" || Boolean(route.meta.public))
</script>
