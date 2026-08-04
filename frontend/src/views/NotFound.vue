<template>
  <div class="not-found">
    <el-result icon="warning" title="404" sub-title="页面不存在或已被删除">
      <template #extra>
        <el-button type="primary" @click="router.push('/dashboard')">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router"

const router = useRouter()
</script>

<style scoped>
.not-found {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
