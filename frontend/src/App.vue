<template>
  <div class="app-root">
    <router-view v-if="isLogin" />
    <MainLayout v-else />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import MainLayout from "@/layouts/MainLayout.vue"

const route = useRoute()
const isLogin = computed(() => route.path === "/login")
</script>
