<template>
  <el-drawer v-model="drawerVisible" title="Skills" size="420px">
    <div class="skills-panel">
      <el-alert
        title="兼容目录式 SKILL.md 包，支持 GitHub tree URL 或 owner/repo:path 方式安装。"
        type="info"
        :closable="false"
        show-icon
      />

      <div v-if="authStore.isSuperAdmin" class="skills-install">
        <el-input
          v-model="installSource"
          placeholder="https://github.com/org/repo/tree/main/path/to/skill 或 owner/repo:path/to/skill"
          clearable
        />
        <el-button
          type="primary"
          :loading="agentStore.installingSkill"
          @click="handleInstall"
        >
          安装 Skill
        </el-button>
      </div>

      <div class="skills-toolbar">
        <span>已发现 {{ agentStore.skills.length }} 个 skills</span>
        <el-button size="small" text :loading="agentStore.loadingSkills" @click="agentStore.fetchSkills()">
          刷新
        </el-button>
      </div>

      <el-empty v-if="!agentStore.loadingSkills && !agentStore.skills.length" description="暂无 skills" />

      <div v-else class="skills-list">
        <div
          v-for="skill in agentStore.skills"
          :key="`${skill.source}-${skill.name}`"
          class="skill-card"
        >
          <div class="skill-header">
            <div>
              <div class="skill-name">{{ skill.name }}</div>
              <div class="skill-source">{{ skill.source }}</div>
            </div>
            <el-tag size="small" :type="skill.source === 'builtin' ? 'success' : 'info'">
              {{ skill.source === "builtin" ? "内置" : "扩展" }}
            </el-tag>
          </div>

          <div class="skill-description">{{ skill.description || "无描述" }}</div>

          <div v-if="skill.allowed_actions?.length" class="skill-actions">
            <el-tag
              v-for="action in skill.allowed_actions"
              :key="`${skill.name}-${action}`"
              size="small"
              effect="plain"
            >
              {{ action }}
            </el-tag>
          </div>

          <div v-if="skill.path" class="skill-path">{{ skill.path }}</div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"

import { useAgentStore } from "@/store/agent"
import { useAuthStore } from "@/store/auth"

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  "update:modelValue": [value: boolean]
}>()

const agentStore = useAgentStore()
const authStore = useAuthStore()
const installSource = ref("")

const drawerVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit("update:modelValue", value),
})

onMounted(() => {
  if (!agentStore.skills.length) {
    agentStore.fetchSkills()
  }
})

const handleInstall = async () => {
  const source = installSource.value.trim()
  if (!source) {
    ElMessage.warning("请输入 skill 来源")
    return
  }

  try {
    await agentStore.installSkill(source)
    installSource.value = ""
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || error.message || "Skill 安装失败")
  }
}
</script>

<style scoped>
.skills-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skills-install {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skills-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--app-text-muted);
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skill-card {
  border: 1px solid var(--app-border-light);
  border-radius: 14px;
  padding: 14px;
  background: #fff;
}

.skill-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.skill-name {
  font-weight: 700;
  color: var(--app-text);
}

.skill-source,
.skill-path {
  margin-top: 4px;
  font-size: 12px;
  color: var(--app-text-muted);
  word-break: break-all;
}

.skill-description {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--app-text);
}

.skill-actions {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
