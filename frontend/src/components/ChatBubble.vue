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
  margin-bottom: 16px;
  max-width: 85%;
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
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: #fff;
}

.avatar-assistant {
  background: linear-gradient(135deg, #909399, #606266);
  color: #fff;
}

.chat-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-bubble--user .chat-content {
  align-items: flex-end;
}

.chat-bubble--assistant .chat-content {
  align-items: flex-start;
}

.bubble-text {
  background: #f4f4f5;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

.chat-bubble--user .bubble-text {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-bubble--assistant .bubble-text {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-bottom-left-radius: 4px;
}

.chat-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  color: #909399;
}

.chat-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 12px;
  color: #f56c6c;
}

.chat-time {
  font-size: 12px;
  color: #909399;
}

.assistant-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.sql-collapse {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.sql-collapse :deep(.el-collapse-item__header) {
  padding: 0 12px;
  font-size: 13px;
  height: 40px;
}

.sql-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.sql-code {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 0 0 8px 8px;
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 13px;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.summary-box {
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 8px;
  padding: 12px;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: #67c23a;
  margin-bottom: 8px;
}

.summary-text {
  color: #606266;
  line-height: 1.6;
}

.summary-text.markdown-body {
  font-size: 14px;
}

.summary-text.markdown-body :deep(h1),
.summary-text.markdown-body :deep(h2),
.summary-text.markdown-body :deep(h3) {
  margin: 12px 0 8px;
  font-weight: 600;
  color: #303133;
}

.summary-text.markdown-body :deep(h1) { font-size: 18px; }
.summary-text.markdown-body :deep(h2) { font-size: 16px; }
.summary-text.markdown-body :deep(h3) { font-size: 15px; }

.summary-text.markdown-body :deep(p) {
  margin: 8px 0;
}

.summary-text.markdown-body :deep(ul),
.summary-text.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.summary-text.markdown-body :deep(li) {
  margin: 4px 0;
}

.summary-text.markdown-body :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: "Fira Code", monospace;
  font-size: 13px;
}

.summary-text.markdown-body :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.summary-text.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
}

.summary-text.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.summary-text.markdown-body :deep(th),
.summary-text.markdown-body :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 8px 12px;
  text-align: left;
}

.summary-text.markdown-body :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}

.summary-text.markdown-body :deep(strong) {
  font-weight: 600;
  color: #303133;
}

.chart-container,
.table-container {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.recommendations {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.rec-label {
  font-size: 13px;
  color: #909399;
}
</style>
