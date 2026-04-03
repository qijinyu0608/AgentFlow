<template>
  <div class="desktop-shell">
    <WorkbenchSidebar
      :collapsed="isTaskListCollapsed"
      :current-view="currentView"
      :can-open-detail="canOpenDetail"
      :sessions-count="sessions.length"
      :grouped-sessions="groupedSessions"
      :active-session-id="activeSessionId"
      :renaming-session-id="renamingSessionId"
      :rename-draft="renameDraft"
      :get-session-subtitle="getSessionSubtitle"
      :format-sidebar-time="formatSidebarTime"
      @new-session="createNewSession"
      @open-view="handleSidebarViewChange"
      @select-session="selectSession"
      @update:rename-draft="renameDraft = $event"
      @start-rename="startRenameSession"
      @confirm-rename="confirmRenameSession"
      @cancel-rename="cancelRenameSession"
      @delete-session="deleteSession"
    />

    <div class="desktop-main">
      <WorkbenchHeader
        :title="currentHeaderTitle"
        :subtitle="currentHeaderSubtitle"
        :ws-status="wsStatus"
        :ws-label="wsStatusLabel"
        :is-agent-running="isAgentRunning"
        :current-task-id="currentTaskId"
        :show-back="showHeaderBack"
        :show-export="canExportConversation"
        @toggle-sidebar="toggleTaskList"
        @back="handleHeaderBack"
        @create-session="createNewSession"
        @export-markdown="exportConversationMarkdown"
      />

      <main class="desktop-content">
        <section v-if="showLongTermMemory" class="page-shell page-shell--flush">
          <div class="page-shell-body page-shell-body--flush">
            <LongTermMemoryPage ref="longTermMemoryRef" />
          </div>
        </section>

        <section v-else-if="showConfig" class="page-shell page-shell--flush">
          <div class="page-shell-body page-shell-body--flush">
            <ConfigTeamModelPage :key="configPageKey" @saved="handleConfigSaved" />
          </div>
        </section>

        <section v-else-if="showRagUpload" class="page-shell page-shell--flush">
          <div class="page-shell-body page-shell-body--flush">
            <RagUploadPage />
          </div>
        </section>

        <section v-else-if="showDetail" class="page-shell page-shell--flush">
          <div class="page-shell-body page-shell-body--flush">
            <TaskCollaborationDetailPage :task-id="currentTaskId" />
          </div>
        </section>

        <WelcomeStage
          v-else-if="!hasSessionContent"
          ref="activeComposerRef"
          title="开始构建"
          subtitle="面向复杂任务的专业协作工作台"
          :workspace-label="workspaceLabel"
          :model-value="inputMessage"
          :selected-team="selectedTeam"
          :available-teams="availableTeams"
          :use-runtime-tools-override="useRuntimeToolsOverride"
          :use-runtime-skills-override="useRuntimeSkillsOverride"
          :loading="isLoading"
          :example-prompts="examplePrompts"
          @update:model-value="inputMessage = $event"
          @update:selected-team="selectedTeam = $event"
          @update:use-runtime-tools-override="useRuntimeToolsOverride = $event"
          @update:use-runtime-skills-override="useRuntimeSkillsOverride = $event"
          @keydown="handleKeyDown"
          @send="sendMessage"
          @set-example="setInputValue"
          @open-memory="openLongTermMemoryView"
          @open-config="openConfigView"
          @open-rag="openRagUploadView"
        />

        <ConversationWorkspace
          v-else
          ref="activeComposerRef"
          :workflow-events="workflowEvents"
          :agent-messages="agentMessages"
          :active-tools="activeTools"
          :selected-tool="selectedTool"
          :selected-tool-data="selectedToolData"
          :selected-team="selectedTeam"
          :available-teams="availableTeams"
          :available-runtime-tools="availableRuntimeTools"
          :available-skills="availableSkills"
          :selected-team-agents="selectedTeamAgents"
          :selected-team-agent-profiles="selectedTeamAgentProfiles"
          :use-runtime-tools-override="useRuntimeToolsOverride"
          :use-runtime-skills-override="useRuntimeSkillsOverride"
          :configurable-selected-runtime-tools="configurableSelectedRuntimeTools"
          :runtime-tool-presets="runtimeToolPresets"
          :runtime-tool-preset="runtimeToolPreset"
          :runtime-tool-field-defs="runtimeToolFieldDefs"
          :current-task-id="currentTaskId"
          :model-value="inputMessage"
          :loading="isLoading"
          :is-compact="isCompactWorkbench"
          :secondary-panel="secondaryPanel"
          :set-messages-container="setMessagesContainer"
          :format-log-time="formatLogTime"
          :format-response="formatResponse"
          :workflow-handoff-payload="workflowHandoffPayload"
          :format-workflow-json="formatWorkflowJson"
          :format-capability-list="formatCapabilityList"
          :get-agent-default-tools="getAgentDefaultTools"
          :get-agent-selected-tools="getAgentSelectedTools"
          :is-tool-selected-for-agent="isToolSelectedForAgent"
          :toggle-agent-runtime-tool="toggleAgentRuntimeTool"
          :apply-runtime-tool-preset="applyRuntimeToolPreset"
          :reset-runtime-tool-configs-to-base="resetRuntimeToolConfigsToBase"
          :get-runtime-tool-meta="getRuntimeToolMeta"
          :get-runtime-tool-config-value="getRuntimeToolConfigValue"
          :update-runtime-tool-config-value="updateRuntimeToolConfigValue"
          :is-runtime-skill-selected-for-agent="isRuntimeSkillSelectedForAgent"
          :get-agent-selected-skills="getAgentSelectedSkills"
          :toggle-agent-runtime-skill="toggleAgentRuntimeSkill"
          @open-detail="openDetailView"
          @update:selected-tool="selectedTool = $event"
          @update:selected-team="selectedTeam = $event"
          @update:use-runtime-tools-override="useRuntimeToolsOverride = $event"
          @update:use-runtime-skills-override="useRuntimeSkillsOverride = $event"
          @update:model-value="inputMessage = $event"
          @update:secondary-panel="secondaryPanel = $event"
          @keydown="handleKeyDown"
          @send="sendMessage"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useWindowSize } from '@vueuse/core'
import ConversationWorkspace from './components/ConversationWorkspace.vue'
import WelcomeStage from './components/WelcomeStage.vue'
import WorkbenchHeader from './components/WorkbenchHeader.vue'
import WorkbenchSidebar from './components/WorkbenchSidebar.vue'
import { getApiBase, getWsBase } from './composables/useApiBase'
import { useTaskStream } from './composables/useTaskStream'
import ConfigTeamModelPage from './pages/ConfigTeamModelPage.vue'
import LongTermMemoryPage from './pages/LongTermMemoryPage.vue'
import RagUploadPage from './pages/RagUploadPage.vue'
import TaskCollaborationDetailPage from './pages/TaskCollaborationDetailPage.vue'
import { useSessionStore } from './stores/sessionStore'

const { width } = useWindowSize()

const isTaskListCollapsed = ref(false)
const inputMessage = ref('')
const isLoading = ref(false)
const messages = ref([])
const tasks = ref([])
const messagesContainer = ref(null)
const activeComposerRef = ref(null)
const isAgentRunning = ref(false)
const selectedTool = ref(null)
const activeTools = ref([])
const agentMessages = ref([])
const workflowEvents = ref([])
const showDetail = ref(false)
const showLongTermMemory = ref(false)
const longTermMemoryRef = ref(null)
const showConfig = ref(false)
const configPageKey = ref(0)
const showRagUpload = ref(false)
const secondaryPanel = ref('dispatch')

const confirmLeaveLongTermMemoryIfNeeded = async () => {
  if (!showLongTermMemory.value) return true
  try {
    return (await longTermMemoryRef.value?.confirmDiscardIfNeeded?.()) ?? true
  } catch {
    return true
  }
}

const leaveSecondaryViews = async () => {
  if (!(await confirmLeaveLongTermMemoryIfNeeded())) return false
  showLongTermMemory.value = false
  showConfig.value = false
  showRagUpload.value = false
  showDetail.value = false
  return true
}

const openConversationHome = async () => leaveSecondaryViews()

const openLongTermMemoryView = async () => {
  showConfig.value = false
  showRagUpload.value = false
  showDetail.value = false
  showLongTermMemory.value = true
}

const closeLongTermMemoryView = async () => {
  if (!(await confirmLeaveLongTermMemoryIfNeeded())) return
  showLongTermMemory.value = false
}

const openConfigView = async () => {
  if (!(await confirmLeaveLongTermMemoryIfNeeded())) return
  showLongTermMemory.value = false
  showRagUpload.value = false
  showDetail.value = false
  showConfig.value = true
}

const closeConfigView = () => {
  showConfig.value = false
}

const openRagUploadView = async () => {
  if (!(await confirmLeaveLongTermMemoryIfNeeded())) return
  showLongTermMemory.value = false
  showConfig.value = false
  showDetail.value = false
  showRagUpload.value = true
}

const closeRagUploadView = () => {
  showRagUpload.value = false
}

const openDetailView = async () => {
  if (!(await confirmLeaveLongTermMemoryIfNeeded())) return
  showLongTermMemory.value = false
  showConfig.value = false
  showRagUpload.value = false
  showDetail.value = true
}

const sessions = ref([])
const activeSessionId = ref(null)
const renamingSessionId = ref(null)
const renameDraft = ref('')
const sessionStore = useSessionStore()

const currentTaskId = ref(null)
const selectedTeam = ref('single_chain_team')
const availableTeams = ref([
  { id: 'single_chain_team', name: 'single_chain_team' },
  { id: 'general_team', name: 'general_team' },
  { id: 'software_team', name: 'software_team' },
])
const availableSkills = ref([])
const availableRuntimeTools = ref([])
const teamAgentProfilesMap = ref({})
const useRuntimeToolsOverride = ref(false)
const selectedRuntimeToolsByAgent = ref({})
const useRuntimeSkillsOverride = ref(false)
const selectedRuntimeSkillsByAgent = ref({})
const runtimeToolConfigDrafts = ref({})
const runtimeToolPreset = ref('balanced')

const bindRefs = () => ({
  messages,
  tasks,
  workflowEvents,
  agentMessages,
  activeTools,
  selectedTool,
  currentTaskId,
  selectedTeam,
  isAgentRunning,
  isLoading,
})

const syncSessionStoreRefs = () => {
  sessions.value = sessionStore.sessions.value
  activeSessionId.value = sessionStore.activeSessionId.value
}

const focusComposer = () => {
  nextTick(() => activeComposerRef.value?.focus?.())
}

const setMessagesContainer = (el) => {
  messagesContainer.value = el
}

const showSessionError = (message, error) => {
  console.error(message, error)
  window.alert(`${message}${error?.message ? `：${error.message}` : ''}`)
}

const resetComposerState = () => {
  inputMessage.value = ''
  messages.value = []
  tasks.value = []
  workflowEvents.value = []
  agentMessages.value = []
  activeTools.value = []
  selectedTool.value = null
  currentTaskId.value = null
  isAgentRunning.value = false
  isLoading.value = false
  secondaryPanel.value = 'dispatch'
}

const createPersistedSession = async () => {
  await sessionStore.createNewSession(bindRefs())
  syncSessionStoreRefs()
}

const createNewSession = async () => {
  if (!(await leaveSecondaryViews())) return
  try {
    closeSessionTaskStream()
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.activeSessionId.value = null
    resetComposerState()
    sessionStore.save()
    syncSessionStoreRefs()
    focusComposer()
  } catch (e) {
    showSessionError('新建会话失败', e)
  }
}

const selectSession = async (id) => {
  if (!(await leaveSecondaryViews())) return
  try {
    closeSessionTaskStream()
    currentTaskId.value = null
    workflowEvents.value = []
    agentMessages.value = []
    await sessionStore.selectSession(bindRefs(), id)
    syncSessionStoreRefs()
  } catch (e) {
    showSessionError('加载会话失败', e)
  }
}

const startRenameSession = (session) => {
  if (session?.id) {
    void selectSession(session.id)
  }
  renamingSessionId.value = session.id
  renameDraft.value = session.title || ''
  nextTick(() => {
    const el = document.querySelector('.thread-rename-input')
    el?.focus?.()
    el?.select?.()
  })
}

const cancelRenameSession = () => {
  renamingSessionId.value = null
  renameDraft.value = ''
}

const confirmRenameSession = async (id) => {
  const nextName = (renameDraft.value || '').trim()
  if (nextName) {
    try {
      await sessionStore.renameSession(id, nextName)
      syncSessionStoreRefs()
    } catch (e) {
      showSessionError('重命名会话失败', e)
    }
  }
  cancelRenameSession()
}

const deleteSession = async (id) => {
  const session = sessionStore.getSessionById(id)
  if (!session) return
  const ok = window.confirm(`确认彻底删除对话「${session.title || '未命名'}」？这会删除消息历史和关联记录，且不可恢复。`)
  if (!ok) return
  try {
    await sessionStore.deleteSession(bindRefs(), id)
    syncSessionStoreRefs()
  } catch (e) {
    showSessionError('彻底删除会话失败', e)
  }
}

const runtimeToolFieldDefs = {
  bash: [
    { key: 'timeout', type: 'number', label: '超时时间（秒）', min: 5, max: 300, step: 5, placeholder: '默认 30 秒', help: '命令执行超过该时间后会自动终止。' },
    { key: 'cwd', type: 'text', label: '工作目录', placeholder: '默认使用当前工作区', help: '相对路径会从当前工作区开始解析。' },
    { key: 'safety_mode', type: 'boolean', label: '安全模式', help: '开启后会拦截明显危险的 bash 命令。' },
  ],
  terminal: [
    { key: 'timeout', type: 'number', label: '超时时间（秒）', min: 5, max: 300, step: 5, placeholder: '默认 30 秒', help: '终端命令的默认执行超时时间。' },
  ],
  read: [
    { key: 'cwd', type: 'text', label: '读取根目录', placeholder: '默认使用当前工作区', help: '用于限定相对路径的起点。' },
  ],
  write: [
    { key: 'cwd', type: 'text', label: '写入根目录', placeholder: '默认使用当前工作区', help: '用于限定相对路径的起点。' },
  ],
  edit: [
    { key: 'cwd', type: 'text', label: '编辑根目录', placeholder: '默认使用当前工作区', help: '用于限定相对路径的起点。' },
  ],
  browser: [
    { key: 'headless', type: 'boolean', label: '无头模式', help: '开启后浏览器在后台运行，更适合自动执行。' },
    { key: 'highlight_elements', type: 'boolean', label: '高亮可交互元素', help: '开启后会在页面中高亮可操作元素，便于调试。' },
  ],
}

const runtimeToolPresets = [
  {
    key: 'balanced',
    label: '平衡',
    description: '适合大多数任务，保留默认安全边界。',
    values: {
      bash: { timeout: 30, safety_mode: true },
      terminal: { timeout: 30 },
      browser: { headless: true, highlight_elements: true },
    },
  },
  {
    key: 'fast',
    label: '快速',
    description: '更短的超时，适合轻量试跑和快速验证。',
    values: {
      bash: { timeout: 15, safety_mode: true },
      terminal: { timeout: 15 },
      browser: { headless: true, highlight_elements: false },
    },
  },
  {
    key: 'deep',
    label: '深度',
    description: '更长的执行时间，更适合复杂命令和深度探索。',
    values: {
      bash: { timeout: 90, safety_mode: true },
      terminal: { timeout: 90 },
      browser: { headless: true, highlight_elements: true },
    },
  },
]

const selectedTeamAgentProfiles = computed(() => {
  const agents = teamAgentProfilesMap.value?.[selectedTeam.value]
  return Array.isArray(agents) ? agents : []
})

const selectedTeamAgents = computed(() => selectedTeamAgentProfiles.value.map((agent) => agent.name).filter(Boolean))

const uniqueCapabilityNames = (values) => {
  const safe = Array.isArray(values) ? values : []
  return Array.from(new Set(safe.map((item) => String(item || '').trim()).filter(Boolean)))
}

const formatCapabilityList = (values) => {
  const items = uniqueCapabilityNames(values)
  return items.length ? items.join('、') : '无'
}

const getAgentProfile = (agentName) => selectedTeamAgentProfiles.value.find((agent) => agent?.name === agentName) || null

const getAgentDefaultTools = (agentName) => uniqueCapabilityNames(getAgentProfile(agentName)?.tools || [])
const getAgentDefaultSkills = (agentName) => uniqueCapabilityNames(getAgentProfile(agentName)?.skills || [])
const getAgentSelectedTools = (agentName) => uniqueCapabilityNames(selectedRuntimeToolsByAgent.value?.[agentName] || [])
const getAgentSelectedSkills = (agentName) => uniqueCapabilityNames(selectedRuntimeSkillsByAgent.value?.[agentName] || [])

const selectedRuntimeToolNames = computed(() => {
  const names = new Set()
  for (const agentName of Object.keys(selectedRuntimeToolsByAgent.value || {})) {
    const toolNames = selectedRuntimeToolsByAgent.value?.[agentName]
    if (!Array.isArray(toolNames)) continue
    for (const toolName of toolNames) {
      if (toolName) names.add(toolName)
    }
  }
  return Array.from(names)
})

const configurableSelectedRuntimeTools = computed(() =>
  selectedRuntimeToolNames.value.filter((toolName) => Array.isArray(runtimeToolFieldDefs[toolName]))
)

const getDayStart = (value) => {
  const date = value instanceof Date ? new Date(value) : new Date(value)
  date.setHours(0, 0, 0, 0)
  return date
}

const groupedSessions = computed(() => {
  const now = new Date()
  const todayStart = getDayStart(now)
  const yesterdayStart = new Date(todayStart)
  yesterdayStart.setDate(yesterdayStart.getDate() - 1)
  const recentStart = new Date(todayStart)
  recentStart.setDate(recentStart.getDate() - 7)

  const groups = [
    { key: 'today', label: '今天', items: [] },
    { key: 'yesterday', label: '昨天', items: [] },
    { key: 'recent', label: '近 7 天', items: [] },
    { key: 'earlier', label: '更早', items: [] },
  ]

  for (const session of sessions.value || []) {
    const updatedAt = new Date(session?.updatedAt || session?.createdAt || Date.now())
    if (updatedAt >= todayStart) {
      groups[0].items.push(session)
    } else if (updatedAt >= yesterdayStart) {
      groups[1].items.push(session)
    } else if (updatedAt >= recentStart) {
      groups[2].items.push(session)
    } else {
      groups[3].items.push(session)
    }
  }

  return groups.filter((group) => group.items.length > 0)
})

const ensureAgentToolState = (agentName) => {
  if (!agentName) return []
  if (!Array.isArray(selectedRuntimeToolsByAgent.value[agentName])) {
    selectedRuntimeToolsByAgent.value[agentName] = []
  }
  return selectedRuntimeToolsByAgent.value[agentName]
}

const ensureAgentSkillState = (agentName) => {
  if (!agentName) return []
  if (!Array.isArray(selectedRuntimeSkillsByAgent.value[agentName])) {
    selectedRuntimeSkillsByAgent.value[agentName] = []
  }
  return selectedRuntimeSkillsByAgent.value[agentName]
}

const getRuntimeToolMeta = (toolName) =>
  (availableRuntimeTools.value || []).find((tool) => tool?.name === toolName) || null

const getBaseRuntimeToolConfig = (toolName) => {
  const cfg = getRuntimeToolMeta(toolName)?.config
  return cfg && typeof cfg === 'object' && !Array.isArray(cfg) ? cfg : {}
}

const ensureRuntimeToolConfigDraft = (toolName) => {
  if (!toolName) return {}
  if (!runtimeToolConfigDrafts.value[toolName] || typeof runtimeToolConfigDrafts.value[toolName] !== 'object') {
    runtimeToolConfigDrafts.value[toolName] = {}
  }
  return runtimeToolConfigDrafts.value[toolName]
}

const mergeRuntimeToolConfigDraft = (toolName, source = {}) => {
  const draft = ensureRuntimeToolConfigDraft(toolName)
  const fieldDefs = runtimeToolFieldDefs[toolName] || []
  for (const field of fieldDefs) {
    if (Object.prototype.hasOwnProperty.call(source || {}, field.key)) {
      draft[field.key] = source[field.key]
    } else if (!Object.prototype.hasOwnProperty.call(draft, field.key) && field.type === 'boolean') {
      draft[field.key] = false
    }
  }
}

const syncRuntimeToolConfigDrafts = () => {
  const next = {}
  for (const toolName of Object.keys(runtimeToolFieldDefs)) {
    const existing = runtimeToolConfigDrafts.value?.[toolName]
    const merged = {
      ...getBaseRuntimeToolConfig(toolName),
      ...(existing && typeof existing === 'object' ? existing : {}),
    }
    next[toolName] = merged
  }
  runtimeToolConfigDrafts.value = next
  for (const toolName of Object.keys(next)) {
    mergeRuntimeToolConfigDraft(toolName, next[toolName])
  }
}

const getRuntimeToolConfigValue = (toolName, fieldKey, fallback = '') => {
  const draft = runtimeToolConfigDrafts.value?.[toolName]
  if (draft && Object.prototype.hasOwnProperty.call(draft, fieldKey)) {
    return draft[fieldKey]
  }
  return fallback
}

const updateRuntimeToolConfigValue = (toolName, fieldKey, value) => {
  const draft = ensureRuntimeToolConfigDraft(toolName)
  draft[fieldKey] = value
}

const applyRuntimeToolPreset = (presetKey) => {
  const preset = runtimeToolPresets.find((item) => item.key === presetKey)
  if (!preset) return
  runtimeToolPreset.value = presetKey
  const targetTools = configurableSelectedRuntimeTools.value.length
    ? configurableSelectedRuntimeTools.value
    : Object.keys(runtimeToolFieldDefs)
  for (const toolName of targetTools) {
    const baseConfig = getBaseRuntimeToolConfig(toolName)
    runtimeToolConfigDrafts.value[toolName] = { ...baseConfig, ...(preset.values?.[toolName] || {}) }
    mergeRuntimeToolConfigDraft(toolName, runtimeToolConfigDrafts.value[toolName])
  }
}

const resetRuntimeToolConfigsToBase = () => {
  const targetTools = configurableSelectedRuntimeTools.value.length
    ? configurableSelectedRuntimeTools.value
    : Object.keys(runtimeToolFieldDefs)
  for (const toolName of targetTools) {
    runtimeToolConfigDrafts.value[toolName] = { ...getBaseRuntimeToolConfig(toolName) }
    mergeRuntimeToolConfigDraft(toolName, runtimeToolConfigDrafts.value[toolName])
  }
}

const buildRuntimeToolConfigsPayload = () => {
  const payload = {}
  for (const toolName of configurableSelectedRuntimeTools.value) {
    const draft = runtimeToolConfigDrafts.value?.[toolName] || {}
    const fields = runtimeToolFieldDefs[toolName] || []
    const next = {}
    for (const field of fields) {
      const raw = draft[field.key]
      if (field.type === 'boolean') {
        if (raw === undefined) continue
        next[field.key] = Boolean(raw)
        continue
      }
      if (field.type === 'number') {
        if (raw === '' || raw === null || raw === undefined) continue
        const num = Number(raw)
        if (Number.isNaN(num)) throw new Error(`${toolName} 的「${field.label}」必须是数字`)
        if (field.min !== undefined && num < field.min) throw new Error(`${toolName} 的「${field.label}」不能小于 ${field.min}`)
        if (field.max !== undefined && num > field.max) throw new Error(`${toolName} 的「${field.label}」不能大于 ${field.max}`)
        next[field.key] = num
        continue
      }
      const text = String(raw ?? '').trim()
      if (!text) continue
      next[field.key] = text
    }
    if (Object.keys(next).length > 0) {
      payload[toolName] = next
    }
  }
  return payload
}

const isToolSelectedForAgent = (agentName, toolName) => {
  if (!agentName || !toolName) return false
  const arr = useRuntimeToolsOverride.value ? ensureAgentToolState(agentName) : getAgentDefaultTools(agentName)
  return arr.includes(toolName)
}

const isRuntimeSkillSelectedForAgent = (agentName, skillName) => {
  if (!agentName || !skillName) return false
  const arr = useRuntimeSkillsOverride.value ? ensureAgentSkillState(agentName) : getAgentDefaultSkills(agentName)
  return arr.includes(skillName)
}

const toggleAgentRuntimeTool = (agentName, toolName, checked) => {
  if (!agentName || !toolName) return
  const arr = ensureAgentToolState(agentName)
  if (checked && !arr.includes(toolName)) {
    arr.push(toolName)
    if (runtimeToolFieldDefs[toolName]) {
      mergeRuntimeToolConfigDraft(toolName, getBaseRuntimeToolConfig(toolName))
    }
  }
  if (!checked) {
    selectedRuntimeToolsByAgent.value[agentName] = arr.filter((name) => name !== toolName)
  }
}

const toggleAgentRuntimeSkill = (agentName, skillName, checked) => {
  if (!agentName || !skillName) return
  const arr = ensureAgentSkillState(agentName)
  if (checked && !arr.includes(skillName)) {
    arr.push(skillName)
  }
  if (!checked) {
    selectedRuntimeSkillsByAgent.value[agentName] = arr.filter((name) => name !== skillName)
  }
}

const normalizeSelectedRuntimeToolsByAgent = () => {
  const validAgents = new Set(selectedTeamAgents.value)
  const validTools = new Set((availableRuntimeTools.value || []).map((tool) => tool?.name).filter(Boolean))
  const next = {}
  for (const agentName of validAgents) {
    const raw = selectedRuntimeToolsByAgent.value?.[agentName]
    const safe = Array.isArray(raw) ? raw : []
    next[agentName] = safe.filter((name) => validTools.has(name))
  }
  selectedRuntimeToolsByAgent.value = next
  syncRuntimeToolConfigDrafts()
}

const normalizeSelectedRuntimeSkillsByAgent = () => {
  const validAgents = new Set(selectedTeamAgents.value)
  const validSkills = new Set((availableSkills.value || []).map((item) => item?.name).filter(Boolean))
  const next = {}
  for (const agentName of validAgents) {
    const raw = selectedRuntimeSkillsByAgent.value?.[agentName]
    const safe = Array.isArray(raw) ? raw : []
    next[agentName] = safe.filter((name) => validSkills.has(name))
  }
  selectedRuntimeSkillsByAgent.value = next
}

const hydrateRuntimeToolsFromTeamDefaults = () => {
  const next = {}
  for (const agent of selectedTeamAgentProfiles.value) {
    next[agent.name] = uniqueCapabilityNames(agent.tools)
  }
  selectedRuntimeToolsByAgent.value = next
  normalizeSelectedRuntimeToolsByAgent()
}

const hydrateRuntimeSkillsFromTeamDefaults = () => {
  const next = {}
  for (const agent of selectedTeamAgentProfiles.value) {
    next[agent.name] = uniqueCapabilityNames(agent.skills)
  }
  selectedRuntimeSkillsByAgent.value = next
  normalizeSelectedRuntimeSkillsByAgent()
}

const loadAvailableTeams = async () => {
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/config`)
    const json = await res.json().catch(() => null)
    if (!res.ok) throw new Error(json?.detail || json?.message || `HTTP ${res.status}`)

    const teamsObj = json?.data?.teams || {}
    const discoveredSkills = Array.isArray(json?.data?.discovered_skills) ? json.data.discovered_skills : []
    const list = Object.entries(teamsObj).map(([id]) => ({ id, name: id }))
    const agentProfilesMap = {}
    for (const [id, team] of Object.entries(teamsObj)) {
      const agents = Array.isArray(team?.agents) ? team.agents : []
      agentProfilesMap[id] = agents
        .map((agent) => ({
          name: String(agent?.name || '').trim(),
          tools: Array.isArray(agent?.tools) ? agent.tools.map((tool) => String(tool || '').trim()).filter(Boolean) : [],
          skills: Array.isArray(agent?.skills) ? agent.skills.map((skill) => String(skill || '').trim()).filter(Boolean) : [],
        }))
        .filter((agent) => agent.name)
    }

    if (list.length) {
      availableTeams.value = list
      availableSkills.value = discoveredSkills
      teamAgentProfilesMap.value = agentProfilesMap
      if (!availableTeams.value.some((team) => team.id === selectedTeam.value)) {
        selectedTeam.value = availableTeams.value[0]?.id || selectedTeam.value
      }
      if (useRuntimeToolsOverride.value) {
        hydrateRuntimeToolsFromTeamDefaults()
      } else {
        normalizeSelectedRuntimeToolsByAgent()
      }
      hydrateRuntimeSkillsFromTeamDefaults()
    }
  } catch {
    // Keep fallback teams if config endpoint is unavailable.
  }
}

const loadAvailableTools = async () => {
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/tools`)
    const json = await res.json().catch(() => null)
    if (!res.ok) throw new Error(json?.detail || json?.message || `HTTP ${res.status}`)
    availableRuntimeTools.value = Array.isArray(json?.data?.tools) ? json.data.tools : []
    normalizeSelectedRuntimeToolsByAgent()
    syncRuntimeToolConfigDrafts()
  } catch {
    availableRuntimeTools.value = []
  }
}

const handleConfigSaved = async () => {
  await loadAvailableTeams()
  await loadAvailableTools()
}

const refreshConfigPage = () => {
  configPageKey.value += 1
}

const refreshLongTermMemory = () => {
  try {
    longTermMemoryRef.value?.load?.()
  } catch {
    // ignore
  }
}

const { ws, wsStatus, connectProcessSocket, close: closeWs } = useTaskStream()
let sessionTaskStreamWs = null

const examplePrompts = [
  '帮我梳理一个新功能从需求到上线的实施方案',
  '帮我分析这个项目里最值得优化的用户体验问题',
  '帮我实现一个新页面，并说明改动影响',
  '帮我整理一份面向团队同步的技术方案摘要',
]

const workflowEventKey = (taskId, data, timestamp) =>
  `${taskId || ''}-${timestamp || ''}-${data?.seq ?? 0}-${data?.agent || ''}-${data?.phase || ''}`

const isPlainObject = (value) => Boolean(value) && typeof value === 'object' && !Array.isArray(value)

const workflowHandoffPayload = (event) => {
  const payload = event?.meta?.handoff_payload
  return isPlainObject(payload) && Object.keys(payload).length > 0 ? payload : null
}

const formatWorkflowJson = (value) => {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value ?? '')
  }
}

const appendWorkflowEvent = (taskId, data, timestamp) => {
  const key = workflowEventKey(taskId, data, timestamp)
  if (workflowEvents.value.some((item) => item.id === key)) return

  let content = data?.content || ''
  if ((data?.phase || '') === 'memory_precheck') {
    const source = data?.meta?.memory_source_path || ''
    const retrievalMode = data?.meta?.retrieval_mode || ''
    const embeddingModel = data?.meta?.active_embedding_model || ''
    const embeddingProfile = data?.meta?.active_embedding_profile || ''
    if (source) content += `\nsource: ${source}`
    if (retrievalMode) content += `\nretrieval_mode: ${retrievalMode}`
    if (embeddingProfile || embeddingModel) {
      content += `\nembedding: ${embeddingProfile || '-'} / ${embeddingModel || '-'}`
    }
  }
  if ((data?.meta || {}).handoff_summary && !content.includes((data?.meta || {}).handoff_summary)) {
    content += `${content ? '\n' : ''}handoff: ${(data?.meta || {}).handoff_summary}`
  }

  workflowEvents.value.push({
    id: key,
    taskId: taskId || null,
    timestamp: timestamp ? new Date(timestamp) : new Date(),
    seq: data?.seq ?? 0,
    agent: data?.agent || 'system',
    phase: data?.phase || 'event',
    status: data?.status || 'running',
    content,
    meta: data?.meta || {},
  })

  workflowEvents.value.sort((a, b) => (a.seq - b.seq) || (a.timestamp - b.timestamp))
}

const closeSessionTaskStream = () => {
  try {
    sessionTaskStreamWs?.close()
  } catch {
    // ignore
  }
  sessionTaskStreamWs = null
}

const subscribeSessionTaskStream = (taskId) => {
  closeSessionTaskStream()
  if (!taskId) return
  const url = `${getWsBase()}/api/v1/tasks/${encodeURIComponent(taskId)}/stream`
  const taskWs = new WebSocket(url)
  taskWs.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data)
      if (msg?.event !== 'workflow_event') return
      appendWorkflowEvent(msg.task_id, msg.data, msg.timestamp)
      sessionStore.syncSessionFromRefs(bindRefs())
      sessionStore.save()
    } catch {
      // ignore
    }
  }
  sessionTaskStreamWs = taskWs
}

const connectWebSocket = () => {
  const socket = connectProcessSocket()
  socket.onmessage = (evt) => {
    try {
      handleServerMessage(JSON.parse(evt.data))
    } catch (error) {
      console.warn('Invalid WS message', error)
    }
  }
}

const getLatestAgentMessage = (agentName) => {
  for (let index = agentMessages.value.length - 1; index >= 0; index -= 1) {
    const item = agentMessages.value[index]
    if (item?.name === agentName) return item
  }
  return null
}

const upsertAgentMessage = (agentName, patch) => {
  let target = getLatestAgentMessage(agentName)
  if (!target) {
    target = {
      id: `${agentName}-${Date.now()}`,
      name: agentName,
      timestamp: new Date(),
      task: '',
      thinking: '',
      tools: [],
      response: '',
    }
    agentMessages.value.push(target)
  }
  if (patch.timestamp) target.timestamp = new Date(patch.timestamp)
  if (patch.task !== undefined) target.task = patch.task
  if (patch.thinking !== undefined) target.thinking = patch.thinking
  if (patch.response !== undefined) target.response = patch.response
}

const appendAgentResultMessage = (agentName, response, timestamp) => {
  const latest = getLatestAgentMessage(agentName)
  const hasOpenEntry = latest && !latest.response
  if (hasOpenEntry) {
    latest.response = response || ''
    if (timestamp) latest.timestamp = new Date(timestamp)
    return
  }
  agentMessages.value.push({
    id: `${agentName}-${Date.now()}-${Math.random()}`,
    name: agentName,
    timestamp: timestamp ? new Date(timestamp) : new Date(),
    task: '',
    thinking: '',
    tools: [],
    response: response || '',
  })
}

const addToolToAgent = (agentName, tool) => {
  let target = getLatestAgentMessage(agentName)
  if (!target) {
    upsertAgentMessage(agentName, {})
    target = getLatestAgentMessage(agentName)
  }
  target.tools = target.tools || []
  target.tools.push({ id: `${Date.now()}-${Math.random()}`, ...tool })
}

const addActiveTool = (tool) => {
  activeTools.value.unshift(tool)
  if (!selectedTool.value) selectedTool.value = tool.id
}

const handleServerMessage = (msg) => {
  const { event, task_id: taskId, data, timestamp } = msg || {}

  if (event === 'user_task_submit') {
    currentTaskId.value = data?.task_id || taskId || null
    const submittedConversationId = data?.conversation_id || activeSessionId.value
    if (submittedConversationId) activeSessionId.value = submittedConversationId
    const currentSession = sessionStore.getSessionById(activeSessionId.value)
    if (currentSession) {
      currentSession.currentTaskId = currentTaskId.value
      currentSession.latestTaskId = currentTaskId.value
      currentSession.status = data?.status === 'success' ? 'running' : currentSession.status
    }
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  if (event === 'workflow_event') {
    appendWorkflowEvent(taskId, data, timestamp)
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  if (event === 'agent_decision') {
    const agentName = data?.agent_name || data?.agent_id || 'Agent'
    upsertAgentMessage(agentName, { task: data?.sub_task || '', timestamp })
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  if (event === 'agent_thinking') {
    const agentName = data?.agent_id || 'Agent'
    upsertAgentMessage(agentName, { thinking: data?.thought || '', timestamp })
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  if (event === 'tool_decision') {
    const agentName = data?.agent_id || 'Agent'
    const toolName = data?.tool_name || data?.tool_id || 'tool'
    const params = JSON.stringify(data?.parameters || {})
    addToolToAgent(agentName, { name: toolName, params })
    addActiveTool({
      id: `${toolName}-${Date.now()}`,
      name: toolName,
      data: { type: 'terminal', command: toolName, output: `Parameters: ${params}` },
    })
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  if (event === 'tool_execute') {
    const agentName = data?.agent_id || 'Agent'
    const toolName = data?.tool_name || 'tool'
    addActiveTool({
      id: `${toolName}-result-${Date.now()}`,
      name: toolName,
      data: {
        type: 'terminal',
        command: toolName,
        output: typeof data?.tool_result === 'string' ? data.tool_result : JSON.stringify(data?.tool_result || {}, null, 2),
      },
    })
    addToolToAgent(agentName, { name: toolName, params: '(executed)' })
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  if (event === 'agent_result') {
    const agentName = data?.agent_id || 'Agent'
    appendAgentResultMessage(agentName, data?.result || '', timestamp)
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  if (event === 'task_result') {
    const status = data?.status
    isAgentRunning.value = false
    isLoading.value = false
    closeSessionTaskStream()
    const task = tasks.value[0]
    if (task && task.status === 'running') task.status = status === 'success' ? 'completed' : 'failed'
    const currentSession = sessionStore.getSessionById(activeSessionId.value)
    if (currentSession) currentSession.status = status === 'success' ? 'active' : 'failed'
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
  }
}

const toggleTaskList = () => {
  isTaskListCollapsed.value = !isTaskListCollapsed.value
}

const handleSidebarViewChange = async (view) => {
  if (view === 'chat') {
    if (await openConversationHome()) {
      focusComposer()
    }
    return
  }
  if (view === 'memory') {
    await openLongTermMemoryView()
    return
  }
  if (view === 'config') {
    await openConfigView()
    return
  }
  if (view === 'rag') {
    await openRagUploadView()
    return
  }
  if (view === 'detail') {
    await openDetailView()
  }
}

const handleHeaderBack = async () => {
  if (showLongTermMemory.value) {
    await closeLongTermMemoryView()
    return
  }
  if (showConfig.value) {
    closeConfigView()
    return
  }
  if (showRagUpload.value) {
    closeRagUploadView()
    return
  }
  showDetail.value = false
}

const setInputValue = (value) => {
  inputMessage.value = value
  focusComposer()
}

const handleKeyDown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim()) return

  if (!activeSessionId.value) {
    try {
      await createPersistedSession()
    } catch (e) {
      showSessionError('新建会话失败', e)
      return
    }
  }

  if (!activeSessionId.value) return

  const userMessage = {
    id: Date.now(),
    type: 'user',
    sender: '你',
    content: inputMessage.value.trim(),
    timestamp: new Date(),
  }
  messages.value.push(userMessage)

  const newTask = {
    id: Date.now(),
    title: inputMessage.value.substring(0, 50) + (inputMessage.value.length > 50 ? '...' : ''),
    description: inputMessage.value,
    agent: 'Task Coordinator',
    status: 'running',
    timestamp: new Date(),
  }
  tasks.value.unshift(newTask)

  const session = sessionStore.getSessionById(activeSessionId.value)
  if (session && (!session.title || session.title === '新对话')) {
    session.title = newTask.title
    try {
      await sessionStore.renameSession(activeSessionId.value, newTask.title)
      syncSessionStoreRefs()
    } catch (error) {
      console.warn('Failed to sync conversation title to server', error)
    }
  }

  const userInput = inputMessage.value
  inputMessage.value = ''
  isLoading.value = true
  isAgentRunning.value = true
  workflowEvents.value = []
  agentMessages.value = []
  activeTools.value = []
  selectedTool.value = null
  currentTaskId.value = null
  secondaryPanel.value = 'dispatch'
  sessionStore.syncSessionFromRefs(bindRefs())
  sessionStore.save()

  connectWebSocket()
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    await new Promise((resolve) => setTimeout(resolve, 300))
  }

  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    isLoading.value = false
    isAgentRunning.value = false
    newTask.status = 'failed'
    messages.value.push({
      id: Date.now() + 1,
      type: 'system',
      sender: 'AgentMesh',
      content: `WebSocket 未连接成功，请确认后端服务已启动（默认 ${getApiBase()}）。`,
      timestamp: new Date(),
    })
    scrollToBottom()
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
    return
  }

  let runtimeToolConfigsPayload = {}
  if (useRuntimeToolsOverride.value) {
    try {
      runtimeToolConfigsPayload = buildRuntimeToolConfigsPayload()
    } catch (error) {
      isLoading.value = false
      isAgentRunning.value = false
      newTask.status = 'failed'
      messages.value.push({
        id: Date.now() + 1,
        type: 'system',
        sender: 'AgentMesh',
        content: `工具策略校验失败：${error?.message || error}`,
        timestamp: new Date(),
      })
      scrollToBottom()
      sessionStore.syncSessionFromRefs(bindRefs())
      sessionStore.save()
      return
    }
  }

  ws.value.send(JSON.stringify({
    event: 'user_input',
    data: {
      text: userInput,
      conversation_id: activeSessionId.value,
      team: selectedTeam.value,
      runtime_tools_by_agent: useRuntimeToolsOverride.value ? selectedRuntimeToolsByAgent.value : null,
      runtime_skills_by_agent: useRuntimeSkillsOverride.value ? selectedRuntimeSkillsByAgent.value : null,
      tool_configs: useRuntimeToolsOverride.value ? runtimeToolConfigsPayload : {},
    },
  }))

  scrollToBottom()
  sessionStore.syncSessionFromRefs(bindRefs())
  sessionStore.save()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const formatWsStatus = (status) => {
  if (status === 'connected') return '已连接'
  if (status === 'connecting') return '连接中'
  if (status === 'disconnected') return '已断开'
  return status || '-'
}

const formatSidebarTime = (value) => {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  const now = new Date()
  if (getDayStart(date).getTime() === getDayStart(now).getTime()) {
    return new Intl.DateTimeFormat('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date)
  }

  if (date.getFullYear() === now.getFullYear()) {
    return new Intl.DateTimeFormat('zh-CN', {
      month: 'numeric',
      day: 'numeric',
    }).format(date)
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).format(date)
}

const getSessionSubtitle = (session) => {
  const preview = String(session?.preview || '').replace(/\s+/g, ' ').trim()
  const title = String(session?.title || '').replace(/\s+/g, ' ').trim()

  if (preview && preview !== title) return preview
  if (session?.status === 'running') return '正在处理中'
  if (session?.messageCount > 0) return `${session.messageCount} 条消息`
  return '新对话'
}

const formatLogTime = (date) => {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

const formatResponse = (response) => {
  if (!response) return ''
  return response
    .replace(/\n/g, '<br>')
    .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
}

const sanitizeExportBasename = (name) => {
  const base = (name || 'export').replace(/[/\\:*?"<>|]/g, '_').trim() || 'export'
  return base.slice(0, 120)
}

const fmtExportTime = (value) => {
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return String(value || '')
  }
}

const triggerDownloadText = (text, filename) => {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

const exportConversationMarkdown = () => {
  const session = sessionStore.getSessionById(activeSessionId.value)
  const title = session?.title || '对话'
  const lines = []

  lines.push('# AgentMesh 对话导出')
  lines.push('')
  lines.push(`- 导出时间：${fmtExportTime(new Date())}`)
  lines.push(`- 会话标题：${title}`)
  lines.push(`- 团队：\`${selectedTeam.value}\``)
  if (currentTaskId.value) lines.push(`- 任务 ID：\`${currentTaskId.value}\``)
  lines.push('')
  lines.push('> 说明：界面中的“输出结果”会做简单渲染；下方“输出结果（原文）”保留后端推送的原始 Markdown 文本。')
  lines.push('')

  const userMsgs = messages.value.filter((message) => message.type === 'user')
  if (userMsgs.length) {
    lines.push('## 用户输入')
    lines.push('')
    for (const message of userMsgs) {
      lines.push(`### ${fmtExportTime(message.timestamp)}`)
      lines.push('')
      lines.push(message.content || '')
      lines.push('')
    }
  }

  if (workflowEvents.value.length) {
    lines.push('## 协作流程')
    lines.push('')
    for (const event of workflowEvents.value) {
      lines.push(`- **${event.agent}** · \`${event.phase}\` · ${event.status} — ${event.content} · _${fmtExportTime(event.timestamp)}_`)
    }
    lines.push('')
  }

  if (agentMessages.value.length) {
    lines.push('## Agent 输出')
    lines.push('')
    for (const agent of agentMessages.value) {
      lines.push(`### ${agent.name}`)
      lines.push('')
      if (agent.task) {
        lines.push('#### 子任务')
        lines.push('')
        lines.push(agent.task)
        lines.push('')
      }
      if (agent.thinking) {
        lines.push('#### 思考过程')
        lines.push('')
        lines.push(agent.thinking)
        lines.push('')
      }
      if (agent.tools?.length) {
        lines.push('#### 工具调用')
        lines.push('')
        for (const tool of agent.tools) {
          lines.push(`- **${tool.name}**：\`${tool.params}\``)
        }
        lines.push('')
      }
      if (agent.response) {
        lines.push('#### 输出结果（Markdown 原文）')
        lines.push('')
        lines.push(agent.response)
        lines.push('')
      }
      lines.push('---')
      lines.push('')
    }
  }

  if (!userMsgs.length && !workflowEvents.value.length && !agentMessages.value.length) {
    window.alert('当前没有可导出的内容（请先发送任务或等待 Agent 返回）。')
    return
  }

  triggerDownloadText(lines.join('\n'), `agentmesh-${sanitizeExportBasename(title)}-${Date.now()}.md`)
}

const selectedToolData = computed(() => {
  if (!selectedTool.value) return null
  const tool = activeTools.value.find((item) => item.id === selectedTool.value)
  return tool?.data || null
})

const hasSessionContent = computed(() => {
  return (
    (messages.value?.length || 0) > 0 ||
    (agentMessages.value?.length || 0) > 0 ||
    (workflowEvents.value?.length || 0) > 0 ||
    (tasks.value?.length || 0) > 0
  )
})

const isCompactWorkbench = computed(() => width.value < 1180)
const wsStatusLabel = computed(() => formatWsStatus(wsStatus.value))
const selectedTeamLabel = computed(() => availableTeams.value.find((team) => team.id === selectedTeam.value)?.name || selectedTeam.value)
const currentSessionTitle = computed(() => sessionStore.getSessionById(activeSessionId.value)?.title || '新线程')
const workspaceLabel = computed(() => currentSessionTitle.value || 'AgentMesh-main')
const currentView = computed(() => {
  if (showLongTermMemory.value) return 'memory'
  if (showConfig.value) return 'config'
  if (showRagUpload.value) return 'rag'
  if (showDetail.value) return 'detail'
  return hasSessionContent.value ? 'chat' : 'welcome'
})
const currentHeaderTitle = computed(() => {
  if (currentView.value === 'memory') return '长期记忆'
  if (currentView.value === 'config') return '团队与模型配置'
  if (currentView.value === 'rag') return '知识库上传'
  if (currentView.value === 'detail') return '协作详情'
  return hasSessionContent.value ? currentSessionTitle.value : '开始构建'
})
const currentHeaderSubtitle = computed(() => {
  if (currentView.value === 'detail') return currentTaskId.value ? `任务 ${currentTaskId.value}` : '还没有任务 ID'
  if (currentView.value === 'memory') return 'MEMORY.md 的结构化维护区'
  if (currentView.value === 'config') return '统一管理团队、Provider 和 skill'
  if (currentView.value === 'rag') return '上传、标注、切块与历史管理'
  if (hasSessionContent.value) return `${selectedTeamLabel.value} · 三栏工作台`
  return `${selectedTeamLabel.value} · 中央聚焦欢迎页`
})
const showHeaderBack = computed(() => ['memory', 'config', 'rag', 'detail'].includes(currentView.value))
const canOpenDetail = computed(() => Boolean(currentTaskId.value))
const canExportConversation = computed(() => currentView.value === 'chat' && hasSessionContent.value)

onMounted(async () => {
  connectWebSocket()
  await loadAvailableTeams()
  await loadAvailableTools()
  await sessionStore.init(selectedTeam.value)
  syncSessionStoreRefs()
  if (activeSessionId.value) {
    try {
      await sessionStore.selectSession(bindRefs(), activeSessionId.value)
      syncSessionStoreRefs()
    } catch (e) {
      showSessionError('初始化会话失败', e)
    }
  }
  if (!availableTeams.value.some((team) => team.id === selectedTeam.value)) {
    selectedTeam.value = availableTeams.value[0]?.id || selectedTeam.value
  }
  focusComposer()
})

onBeforeUnmount(() => {
  sessionStore.syncSessionFromRefs(bindRefs())
  sessionStore.save()
  closeSessionTaskStream()
  try {
    closeWs()
  } catch {
    // ignore
  }
})

watch(
  () => selectedTeam.value,
  () => {
    if (useRuntimeToolsOverride.value) {
      hydrateRuntimeToolsFromTeamDefaults()
    } else {
      normalizeSelectedRuntimeToolsByAgent()
    }
    hydrateRuntimeSkillsFromTeamDefaults()
    sessionStore.syncSessionFromRefs(bindRefs())
    sessionStore.save()
  }
)

watch(
  () => useRuntimeToolsOverride.value,
  (enabled) => {
    if (enabled) hydrateRuntimeToolsFromTeamDefaults()
  }
)

watch(
  () => useRuntimeSkillsOverride.value,
  () => {
    hydrateRuntimeSkillsFromTeamDefaults()
  }
)

watch(
  () => [activeSessionId.value, currentTaskId.value],
  ([sessionId, taskId]) => {
    if (!sessionId || !taskId) {
      closeSessionTaskStream()
      return
    }
    subscribeSessionTaskStream(taskId)
  },
  { immediate: true }
)

watch(
  () => activeTools.value.length,
  (length, previous = 0) => {
    if (isCompactWorkbench.value && length > previous) {
      secondaryPanel.value = 'tools'
    }
  }
)

watch(
  () => isCompactWorkbench.value,
  (compact) => {
    if (!compact) {
      secondaryPanel.value = 'dispatch'
    }
  }
)
</script>

<style scoped>
.desktop-shell {
  height: 100vh;
  display: flex;
  background: #ffffff;
  color: var(--text-primary);
  overflow: hidden;
}

.desktop-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 12px 12px 10px;
}

.desktop-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-3xl);
  background: #ffffff;
  box-shadow: var(--shadow-large);
  overflow: hidden;
  padding: 18px;
}

.page-shell {
  flex: 1;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.desktop-content > * {
  min-height: 0;
}

.page-shell--flush {
  min-height: 0;
}

.page-shell-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-2xl);
  background: #ffffff;
  padding: 18px;
}

.page-shell-body--flush {
  height: 100%;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
  overflow: hidden;
}

.page-shell-body :deep(.mem),
.page-shell-body :deep(.cfg),
.page-shell-body :deep(.rag),
.page-shell-body :deep(.detail) {
  height: 100%;
  min-height: 100%;
}

.page-shell-body :deep(.top),
.page-shell-body :deep(.header) {
  background: transparent;
  border: 0;
  padding: 0 0 18px;
}

.page-shell-body :deep(.card),
.page-shell-body :deep(.validationCard),
.page-shell-body :deep(.previewCard),
.page-shell-body :deep(.previewCardWide),
.page-shell-body :deep(.timelineCard),
.page-shell-body :deep(.metricsCard),
.page-shell-body :deep(.graphCard) {
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-subtle);
  background: #ffffff;
  box-shadow: none;
}

.page-shell-body :deep(.btn),
.page-shell-body :deep(.primary),
.page-shell-body :deep(.iconBtn) {
  min-height: 38px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: #ffffff;
  color: var(--text-secondary);
  box-shadow: none;
}

.page-shell-body :deep(.primary) {
  background: #111111;
  border-color: #111111;
  color: #ffffff;
}

.page-shell-body :deep(input),
.page-shell-body :deep(textarea),
.page-shell-body :deep(select) {
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: #ffffff;
  color: var(--text-primary);
  box-shadow: none;
}

.page-shell-body :deep(.notice) {
  border-radius: var(--radius-lg);
}

.page-shell-body :deep(pre) {
  font-family: var(--ui-font-mono);
}

:deep(.code-block) {
  overflow: auto;
  padding: 14px;
  border-radius: var(--radius-lg);
  background: rgba(17, 17, 17, 0.05);
  font-family: var(--ui-font-mono);
  font-size: 12px;
  line-height: 1.7;
}

:deep(.inline-code) {
  padding: 0.15em 0.4em;
  border-radius: var(--radius-xs);
  background: rgba(17, 17, 17, 0.06);
  font-family: var(--ui-font-mono);
  font-size: 0.92em;
}

@media (max-width: 1180px) {
  .desktop-main {
    padding: 10px;
  }

  .desktop-content {
    border-radius: var(--radius-2xl);
    padding: 14px;
  }
}

@media (max-width: 860px) {
  .page-shell-head {
    flex-direction: column;
  }
}
</style>
