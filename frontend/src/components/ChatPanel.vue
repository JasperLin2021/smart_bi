<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-header-title">智能对话</span>
        <el-tag v-if="recommendations.length" type="info">推荐维度/指标</el-tag>
      </div>
    </template>
    <div class="chat-panel">
      <div v-for="(message, index) in messages" :key="index" class="chat-message">
        <div
          :class="message.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'"
        >
          {{ message.role === "user" ? "你：" : "助手：" }}
        </div>
        <div>{{ message.content }}</div>
      </div>
      <el-empty v-if="!messages.length" description="输入问题开始分析"></el-empty>
    </div>
    <div v-if="recommendations.length" class="recommendations">
      <el-space wrap>
        <el-tag
          v-for="item in recommendations"
          :key="item"
          type="success"
          effect="plain"
        >
          {{ item }}
        </el-tag>
      </el-space>
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  messages: Array<{ role: "user" | "assistant"; content: string }>
  recommendations: string[]
}>()
</script>
