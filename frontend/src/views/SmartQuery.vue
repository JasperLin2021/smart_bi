<template>
  <div class="smart-query-page">
    <el-row :gutter="16" class="page-row">
      <!-- 主聊天区域 -->
      <el-col :xs="24" :md="17" :lg="18">
        <el-card class="chat-card">
          <!-- 头部 -->
          <template #header>
            <div class="card-header">
              <span class="card-header-title">智能问数助手</span>
              <div class="header-actions">
                <el-radio-group v-model="queryStore.mode" size="small">
                  <el-radio-button label="text2sql">智能问数</el-radio-button>
                  <el-radio-button label="chat">闲聊模式</el-radio-button>
                </el-radio-group>
                <el-button size="small" text @click="clearChat">
                  <el-icon><Delete /></el-icon>
                  清空对话
                </el-button>
              </div>
            </div>
          </template>
          
          <!-- 聊天消息区域 -->
          <div ref="chatContainerRef" class="chat-container">
            <!-- 欢迎消息 -->
            <div v-if="queryStore.messages.length === 0" class="welcome-message">
              <div class="welcome-icon">
                <el-icon :size="48"><ChatDotRound /></el-icon>
              </div>
              <h3>欢迎使用智能问数助手</h3>
              <p>您可以用自然语言提问，我会帮您查询数据并生成分析结果</p>
              <div class="welcome-examples">
                <span class="example-label">试试这样问：</span>
                <el-tag 
                  v-for="example in examples" 
                  :key="example" 
                  type="info" 
                  effect="plain"
                  class="example-tag"
                  @click="useExample(example)"
                >
                  {{ example }}
                </el-tag>
              </div>
            </div>
            
            <!-- 消息列表 -->
            <div v-else class="messages-list">
              <ChatBubble 
                v-for="message in queryStore.messages" 
                :key="message.id" 
                :message="message" 
              />
            </div>
          </div>
          
          <!-- 输入区域 -->
          <div class="input-area">
            <el-input
              v-model="question"
              :placeholder="inputPlaceholder"
              :disabled="queryStore.loading"
              size="large"
              @keyup.enter="submit"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
              <template #append>
                <el-button 
                  type="primary" 
                  :loading="queryStore.loading"
                  :disabled="!question.trim()"
                  @click="submit"
                >
                  <el-icon><Promotion /></el-icon>
                  发送
                </el-button>
              </template>
            </el-input>
            <div class="input-tips">
              <span v-if="queryStore.mode === 'text2sql'">
                提示：输入数据查询相关问题，系统会自动生成SQL并执行
              </span>
              <span v-else>
                提示：闲聊模式下可以进行自由对话
              </span>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- 侧边栏 -->
      <el-col :xs="24" :md="7" :lg="6">
        <el-card class="history-card">
          <template #header>
            <div class="card-header">
              <span class="card-header-title">查询历史</span>
              <el-button size="small" text @click="queryStore.fetchHistory">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>
          <div class="history-list">
            <div 
              v-for="item in queryStore.history" 
              :key="item.id"
              class="history-item"
              @click="viewHistory(item)"
            >
              <div class="history-content">
                <el-icon class="history-icon"><ChatLineSquare /></el-icon>
                <span class="history-text">{{ cleanHistoryText(item.question) }}</span>
              </div>
              <div class="history-meta">
                <span class="history-date">{{ item.created_at }}</span>
                <div class="history-actions">
                  <el-icon 
                    :class="['favorite-icon', { 'is-favorite': item.favorite }]"
                    @click.stop="queryStore.toggleFavorite(item.id)"
                  >
                    <Star v-if="item.favorite" />
                    <StarFilled v-else />
                  </el-icon>
                  <el-icon 
                    class="delete-icon"
                    @click.stop="deleteHistoryItem(item.id)"
                  >
                    <Close />
                  </el-icon>
                </div>
              </div>
            </div>
            <el-empty v-if="!queryStore.history.length" description="暂无历史记录" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue"
import { 
  ChatDotRound, Search, Promotion, Delete, Refresh, 
  ChatLineSquare, Star, StarFilled, Close
} from "@element-plus/icons-vue"
import ChatBubble from "@/components/ChatBubble.vue"
import { useQueryStore } from "@/store/query"

const queryStore = useQueryStore()
const question = ref("")
const chatContainerRef = ref<HTMLDivElement | null>(null)

const examples = [
  "查询最近一周的数据趋势",
  "Top 10 数据统计",
  "各分类数量汇总"
]

const inputPlaceholder = computed(() => {
  return queryStore.mode === "text2sql" 
    ? "输入您的数据查询问题..." 
    : "输入您想聊的内容..."
})

const submit = async () => {
  const q = question.value.trim()
  if (!q || queryStore.loading) return
  
  question.value = ""
  await queryStore.ask(q)
  scrollToBottom()
}

const useExample = (example: string) => {
  question.value = example
}

const viewHistory = async (item: { id: number; question: string }) => {
  // 加载保存的历史记录详情
  await queryStore.loadHistoryDetail(item.id)
  scrollToBottom()
}

const deleteHistoryItem = async (id: number) => {
  await queryStore.deleteHistory(id)
}

const cleanHistoryText = (text: string) => {
  return text.replace(/^\[(SQL|闲聊)\]\s*/, "")
}

const clearChat = () => {
  queryStore.clearMessages()
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainerRef.value) {
    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
  }
}

// 监听消息变化，自动滚动
watch(() => queryStore.messages.length, () => {
  scrollToBottom()
})

onMounted(() => {
  queryStore.fetchHistory()
})
</script>

<style scoped>
.smart-query-page {
  height: calc(100vh - 120px);
}

.page-row {
  height: 100%;
}

.chat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header-title {
  font-weight: 600;
  font-size: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 聊天区域 */
.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: linear-gradient(180deg, #f5f7fa 0%, #fff 100%);
}

/* 欢迎消息 */
.welcome-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #606266;
}

.welcome-icon {
  color: #409eff;
  margin-bottom: 16px;
}

.welcome-message h3 {
  margin: 0 0 8px;
  font-size: 20px;
  color: #303133;
}

.welcome-message p {
  margin: 0 0 24px;
  color: #909399;
}

.welcome-examples {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.example-label {
  width: 100%;
  margin-bottom: 8px;
  font-size: 13px;
  color: #909399;
}

.example-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.example-tag:hover {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

/* 消息列表 */
.messages-list {
  display: flex;
  flex-direction: column;
}

/* 输入区域 */
.input-area {
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

.input-area :deep(.el-input-group__append) {
  background: #409eff;
  border-color: #409eff;
  padding: 0;
}

.input-area :deep(.el-input-group__append .el-button) {
  margin: 0;
  padding: 0 20px;
  height: 100%;
  border: none;
  color: #fff;
}

.input-tips {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

/* 历史记录 */
.history-card {
  height: 100%;
}

.history-card :deep(.el-card__body) {
  padding: 0;
  overflow: hidden;
}

.history-list {
  max-height: calc(100vh - 220px);
  overflow-y: auto;
}

.history-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: #f5f7fa;
}

.history-content {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}

.history-icon {
  flex-shrink: 0;
  color: #909399;
  margin-top: 2px;
}

.history-text {
  font-size: 13px;
  color: #303133;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.history-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-date {
  font-size: 12px;
  color: #c0c4cc;
}

.favorite-icon {
  color: #c0c4cc;
  cursor: pointer;
  transition: color 0.2s;
}

.favorite-icon:hover,
.favorite-icon.is-favorite {
  color: #e6a23c;
}

.delete-icon {
  color: #c0c4cc;
  cursor: pointer;
  transition: color 0.2s;
}

.delete-icon:hover {
  color: #f56c6c;
}
</style>
