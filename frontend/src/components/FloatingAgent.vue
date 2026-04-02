<template>
  <div class="agent-shell">
    <button class="agent-fab" @click="agentStore.toggle()">
      <el-icon><ChatDotRound /></el-icon>
    </button>

    <transition name="agent-panel">
      <div v-if="agentStore.open" class="agent-panel">
        <div class="agent-header">
          <div>
            <div class="agent-title">页面 Agent</div>
            <div class="agent-subtitle">受控执行，按当前账号权限运行</div>
          </div>
          <div class="agent-header-actions">
            <el-button size="small" text @click="skillsVisible = true">Skills</el-button>
            <el-button size="small" text @click="agentStore.reset()">清空</el-button>
            <el-button size="small" text @click="agentStore.toggle()">关闭</el-button>
          </div>
        </div>

        <div class="agent-context">
          <span>页面：{{ route.path }}</span>
          <span v-if="datasourceStore.current">数据源：{{ datasourceStore.current.name }}</span>
        </div>

        <div class="agent-messages">
          <div v-for="message in agentStore.messages" :key="message.id" :class="['agent-message', `agent-message--${message.role}`]">
            <div class="agent-bubble">
              <div class="agent-text">{{ message.content }}</div>
              <div v-if="message.reasoning" class="agent-reasoning">规划依据：{{ message.reasoning }}</div>
              <div v-if="message.skill" class="agent-skill">
                <div class="agent-actions-title">已选 Skill</div>
                <div class="agent-skill-card">
                  <div class="agent-skill-header">
                    <span>{{ message.skill.name }}</span>
                    <el-tag size="small" effect="plain">
                      {{ message.skill.source === "builtin" ? "内置" : "扩展" }}
                    </el-tag>
                  </div>
                  <div class="agent-skill-description">{{ message.skill.description || "无描述" }}</div>
                </div>
              </div>

              <div v-if="message.actions?.length" class="agent-actions">
                <div class="agent-actions-title">执行计划</div>
                <div v-for="action in message.actions" :key="`${message.id}-${action.label}`" class="agent-action-item">
                  <span>{{ action.label }}</span>
                  <el-tag :type="riskTagType(action.risk)" size="small">{{ riskLabel(action.risk) }}</el-tag>
                </div>
              </div>

              <div v-if="message.execution?.length" class="agent-execution">
                <div class="agent-actions-title">执行结果</div>
                <div v-for="item in message.execution" :key="`${message.id}-${item.action}-${item.status}`" class="agent-exec-item">
                  <span>{{ item.action }}</span>
                  <el-tag :type="item.status === 'success' ? 'success' : 'danger'" size="small">
                    {{ item.status === "success" ? "成功" : "失败" }}
                  </el-tag>
                </div>
              </div>

              <div v-if="message.requiresConfirmation && message.actions?.length && !message.execution?.length" class="agent-confirm">
                <el-alert
                  title="该计划包含中高风险动作，执行前需要确认。"
                  type="warning"
                  :closable="false"
                  show-icon
                />
                <el-button
                  type="primary"
                  size="small"
                  :loading="agentStore.executing"
                  @click="agentStore.confirm(message.id)"
                >
                  确认执行
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="agent-input">
          <el-input
            v-model="agentStore.input"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="例如：打开数据源管理；切换到生产数据Excel；查询今天各产线产量"
          />
          <div class="agent-input-actions">
            <span class="agent-tip">低风险动作自动执行，修改删除类动作需要确认。</span>
            <el-button type="primary" :loading="agentStore.planning" @click="agentStore.send()">发送</el-button>
          </div>
        </div>
      </div>
    </transition>

    <AgentSkillsDrawer v-model="skillsVisible" />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { ChatDotRound } from "@element-plus/icons-vue"
import { useRoute } from "vue-router"

import AgentSkillsDrawer from "@/components/AgentSkillsDrawer.vue"
import { useAgentStore } from "@/store/agent"
import { useDatasourceStore } from "@/store/datasource"

const route = useRoute()
const agentStore = useAgentStore()
const datasourceStore = useDatasourceStore()
const skillsVisible = ref(false)

const riskLabel = (risk: string) => {
  if (risk === "high") return "高风险"
  if (risk === "medium") return "需确认"
  return "低风险"
}

const riskTagType = (risk: string) => {
  if (risk === "high") return "danger"
  if (risk === "medium") return "warning"
  return "success"
}
</script>

<style scoped>
.agent-shell {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 3000;
}

.agent-fab {
  width: 58px;
  height: 58px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
  color: white;
  box-shadow: 0 16px 36px rgba(15, 118, 110, 0.32);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.agent-panel {
  position: absolute;
  right: 0;
  bottom: 72px;
  width: 400px;
  height: 640px;
  background: #fff;
  border: 1px solid var(--app-border-light);
  border-radius: 20px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.agent-panel-enter-active,
.agent-panel-leave-active {
  transition: all 0.18s ease;
}

.agent-panel-enter-from,
.agent-panel-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}

.agent-header {
  padding: 16px 18px;
  border-bottom: 1px solid var(--app-border-light);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  background: linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%);
}

.agent-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--app-text);
}

.agent-subtitle {
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.agent-header-actions {
  display: flex;
  gap: 4px;
}

.agent-context {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--app-border-light);
  font-size: 12px;
  color: var(--app-text-muted);
  background: #f8fafc;
}

.agent-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

.agent-message--user {
  display: flex;
  justify-content: flex-end;
}

.agent-message--assistant {
  display: flex;
  justify-content: flex-start;
}

.agent-bubble {
  max-width: 92%;
  border-radius: 16px;
  padding: 12px 14px;
  border: 1px solid var(--app-border-light);
  background: white;
}

.agent-message--user .agent-bubble {
  background: #0f766e;
  color: white;
  border-color: #0f766e;
}

.agent-text {
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 13px;
}

.agent-reasoning {
  margin-top: 8px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.agent-message--user .agent-reasoning {
  color: rgba(255, 255, 255, 0.8);
}

.agent-actions,
.agent-skill,
.agent-execution,
.agent-confirm {
  margin-top: 12px;
}

.agent-actions-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-muted);
  margin-bottom: 8px;
}

.agent-skill-card {
  border-radius: 12px;
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  padding: 10px;
}

.agent-skill-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
}

.agent-skill-description {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--app-text-muted);
}

.agent-action-item,
.agent-exec-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8fafc;
  margin-bottom: 6px;
  font-size: 12px;
}

.agent-input {
  border-top: 1px solid var(--app-border-light);
  padding: 14px 16px;
  background: white;
}

.agent-input-actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.agent-tip {
  font-size: 11px;
  color: var(--app-text-light);
  line-height: 1.4;
}
</style>
