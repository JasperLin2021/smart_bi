<template>
  <div class="chat-bubble" :class="[`chat-bubble--${message.role}`, { 'chat-bubble--error': message.status === 'error' }]">
    <!-- 头像 -->
    <div class="chat-avatar">
      <el-avatar :size="36" :class="message.role === 'user' ? 'avatar-user' : 'avatar-assistant'">
        {{ message.role === 'user' ? '我' : 'AI' }}
      </el-avatar>
    </div>
    
    <!-- 消息内容区 -->
    <div class="chat-content">
      <!-- 加载状态 -->
      <div v-if="message.status === 'sending'" class="chat-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在思考中...</span>
      </div>
      
      <!-- 错误状态 -->
      <div v-else-if="message.status === 'error'" class="chat-error">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ message.error || '请求失败，请重试' }}</span>
      </div>
      
      <!-- 正常消息 -->
      <template v-else>
        <!-- 用户消息 -->
        <div v-if="message.role === 'user'" class="bubble-text">
          {{ message.content }}
        </div>
        
        <!-- 助手消息 -->
        <div v-else class="assistant-content">
          <!-- 文字回复 -->
          <div v-if="message.content" class="bubble-text">
            {{ message.content }}
          </div>
          
          <!-- SQL 查询 (可折叠) -->
          <el-collapse v-if="message.sqlQuery" class="sql-collapse">
            <el-collapse-item title="SQL 查询语句" name="sql">
              <pre class="sql-code">{{ message.sqlQuery }}</pre>
            </el-collapse-item>
          </el-collapse>
          
          <!-- 分析总结 -->
          <div v-if="message.summary && message.summary !== message.content" class="summary-box">
            <div class="summary-title">
              <el-icon><DataAnalysis /></el-icon>
              <span>分析总结</span>
            </div>
            <div class="summary-text markdown-body" v-html="renderedSummary"></div>
          </div>
          
          <!-- 查询结果图表 -->
          <div v-if="hasResult" class="chart-container">
            <MessageChart 
              :columns="message.result!.columns" 
              :rows="message.result!.rows" 
              :sql-query="message.sqlQuery"
            />
          </div>
          
          <!-- 查询结果表格 -->
          <div v-if="hasResult" class="table-container">
            <MessageTable :columns="message.result!.columns" :rows="message.result!.rows" />
          </div>
          
          <!-- 推荐标签 -->
          <div v-if="message.recommendations?.length" class="recommendations">
            <span class="rec-label">推荐维度：</span>
            <el-tag v-for="tag in message.recommendations" :key="tag" type="success" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </template>
      
      <!-- 时间戳 -->
      <div class="chat-time">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Loading, WarningFilled, DataAnalysis } from "@element-plus/icons-vue"
import { marked } from "marked"
import type { ChatMessage } from "@/store/query"
import MessageChart from "./MessageChart.vue"
import MessageTable from "./MessageTable.vue"

const props = defineProps<{
  message: ChatMessage
}>()

const hasResult = computed(() => {
  return props.message.result && 
         props.message.result.rows && 
         props.message.result.rows.length > 0
})

// 渲染 Markdown
const renderedSummary = computed(() => {
  if (!props.message.summary) return ""
  return marked(props.message.summary, { breaks: true })
})

const formatTime = (date: Date) => {
  const d = new Date(date)
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}
</script>

<style scoped>
.chat-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
  animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-bubble--user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.chat-bubble--assistant {
  flex-direction: row;
  margin-right: auto;
}

.chat-avatar {
  flex-shrink: 0;
}

.avatar-user {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-weight: 600;
}

.avatar-assistant {
  background: linear-gradient(135deg, #1e1b4b, #312e81);
  color: #fff;
  font-weight: 600;
}

.chat-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-bubble--user .chat-content {
  align-items: flex-end;
}

.chat-bubble--assistant .chat-content {
  align-items: flex-start;
}

.bubble-text {
  background: var(--app-surface-muted);
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
  font-size: 14px;
}

.chat-bubble--user .bubble-text {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}

.chat-bubble--assistant .bubble-text {
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-bottom-left-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.chat-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 16px;
  color: var(--app-text-muted);
}

.chat-loading .el-icon {
  color: var(--app-primary);
}

.chat-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 16px;
  color: #ef4444;
}

.chat-time {
  font-size: 11px;
  color: var(--app-text-light);
}

.assistant-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
}

.sql-collapse {
  background: var(--app-surface);
  border-radius: 12px;
  border: 1px solid var(--app-border-light);
  overflow: hidden;
}

.sql-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  font-size: 13px;
  height: 44px;
  font-weight: 500;
  color: var(--app-text);
}

.sql-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.sql-code {
  background: #1e1b4b;
  color: #e0e7ff;
  padding: 16px;
  border-radius: 0 0 12px 12px;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 13px;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

.summary-box {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border: 1px solid #a7f3d0;
  border-radius: 12px;
  padding: 16px;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #059669;
  margin-bottom: 10px;
}

.summary-text {
  color: var(--app-text);
  line-height: 1.7;
}

.summary-text.markdown-body {
  font-size: 14px;
}

.summary-text.markdown-body :deep(h1),
.summary-text.markdown-body :deep(h2),
.summary-text.markdown-body :deep(h3) {
  margin: 14px 0 10px;
  font-weight: 600;
  color: var(--app-text);
}

.summary-text.markdown-body :deep(h1) { font-size: 18px; }
.summary-text.markdown-body :deep(h2) { font-size: 16px; }
.summary-text.markdown-body :deep(h3) { font-size: 15px; }

.summary-text.markdown-body :deep(p) {
  margin: 10px 0;
}

.summary-text.markdown-body :deep(ul),
.summary-text.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 10px 0;
}

.summary-text.markdown-body :deep(li) {
  margin: 6px 0;
}

.summary-text.markdown-body :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 13px;
}

.summary-text.markdown-body :deep(pre) {
  background: #1e1b4b;
  color: #e0e7ff;
  padding: 14px;
  border-radius: 8px;
  overflow-x: auto;
}

.summary-text.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
}

.summary-text.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
}

.summary-text.markdown-body :deep(th),
.summary-text.markdown-body :deep(td) {
  border: 1px solid var(--app-border);
  padding: 10px 14px;
  text-align: left;
}

.summary-text.markdown-body :deep(th) {
  background: var(--app-surface-muted);
  font-weight: 600;
}

.summary-text.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--app-text);
}

.chart-container,
.table-container {
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.recommendations {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.rec-label {
  font-size: 13px;
  color: var(--app-text-muted);
  font-weight: 500;
}

.recommendations :deep(.el-tag) {
  border-radius: 20px;
  padding: 4px 12px;
}
</style>
