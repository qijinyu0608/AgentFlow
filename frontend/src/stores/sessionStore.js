import { ref } from 'vue'
import { getApiBase } from '../composables/useApiBase'

const STORAGE_KEY = 'agentmesh:ui-cache:v2'

const toDate = (value) => {
  if (value instanceof Date) return value
  if (typeof value === 'string' || typeof value === 'number') {
    const d = new Date(value)
    if (!Number.isNaN(d.getTime())) return d
  }
  return new Date()
}

const createEmptyRuntimeState = () => ({
  messages: [],
  tasks: [],
  workflowEvents: [],
  agentMessages: [],
  activeTools: [],
  selectedTool: null,
  loaded: false,
})

const normalizeUiCache = (raw) => {
  const sessionMeta = raw?.sessionMeta && typeof raw.sessionMeta === 'object' ? raw.sessionMeta : {}
  return {
    activeSessionId: typeof raw?.activeSessionId === 'string' ? raw.activeSessionId : null,
    sessionMeta,
  }
}

const loadUiCache = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return normalizeUiCache({})
    return normalizeUiCache(JSON.parse(raw))
  } catch (e) {
    console.warn('Failed to load UI cache', e)
    return normalizeUiCache({})
  }
}

const serializeUiCache = (activeSessionId, sessions) => {
  const sessionMeta = {}
  for (const session of sessions || []) {
    if (!session?.id) continue
    sessionMeta[session.id] = {
      selectedTeam: session.selectedTeam || 'single_chain_team',
      currentTaskId: session.currentTaskId || null,
    }
  }
  return { activeSessionId, sessionMeta }
}

const saveUiCache = (activeSessionId, sessions) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serializeUiCache(activeSessionId, sessions)))
  } catch (e) {
    console.warn('Failed to save UI cache', e)
  }
}

const roleToSender = (role) => {
  if (role === 'user') return '你'
  if (role === 'assistant') return 'AgentMesh'
  if (role === 'tool') return '工具'
  return '系统'
}

const mapConversationMessage = (row) => ({
  id: row?.id ?? `${row?.conversation_id || 'msg'}-${row?.seq || 0}`,
  type: row?.role === 'user' ? 'user' : row?.role === 'assistant' ? 'assistant' : 'system',
  sender: roleToSender(row?.role),
  role: row?.role || 'system',
  content: row?.content || '',
  timestamp: toDate(row?.ts),
  meta: row?.meta || {},
})

const mapWorkflowEvent = (row) => {
  const data = row?.data || {}
  const timestamp = toDate(row?.timestamp)
  return {
    id: `${row?.task_id || ''}-${row?.timestamp || ''}-${data?.seq ?? 0}-${data?.agent || ''}-${data?.phase || ''}`,
    taskId: row?.task_id || null,
    timestamp,
    seq: data?.seq ?? 0,
    agent: data?.agent || 'system',
    phase: data?.phase || 'event',
    status: data?.status || 'running',
    content: data?.content || '',
    meta: data?.meta || {},
  }
}

const upsertRecoveredAgent = (list, agentName, patch) => {
  if (!agentName || agentName === 'system' || agentName === 'assistant' || agentName === 'user') {
    return
  }
  let target = list.find((item) => item.name === agentName)
  if (!target) {
    target = {
      id: `recovered-${agentName}`,
      name: agentName,
      timestamp: new Date(),
      task: '',
      thinking: '',
      tools: [],
      response: '',
    }
    list.push(target)
  }
  if (patch.timestamp) target.timestamp = patch.timestamp
  if (patch.task !== undefined && !target.task) target.task = patch.task
  if (patch.thinking !== undefined && !target.thinking) target.thinking = patch.thinking
  if (patch.response !== undefined && !target.response) target.response = patch.response
  if (patch.tool) {
    target.tools.push({
      id: `${target.id}-${target.tools.length + 1}`,
      name: patch.tool.name || 'tool',
      params: patch.tool.params || '',
    })
  }
}

const buildRecoveredAgentMessages = (workflowEvents, messages) => {
  const recovered = []
  for (const ev of workflowEvents || []) {
    const meta = ev?.meta || {}
    if (ev.phase === 'agent_started') {
      upsertRecoveredAgent(recovered, ev.agent, {
        timestamp: ev.timestamp,
        task: meta?.sub_task || ev.content || '',
      })
      continue
    }
    if (ev.phase === 'tool_decided') {
      upsertRecoveredAgent(recovered, ev.agent, {
        timestamp: ev.timestamp,
        tool: {
          name: meta?.tool_name || 'tool',
          params: JSON.stringify(meta?.parameters || {}),
        },
      })
      continue
    }
    if (ev.phase === 'agent_finished') {
      upsertRecoveredAgent(recovered, ev.agent, {
        timestamp: ev.timestamp,
        response: ev.content || '',
      })
    }
  }

  const latestAssistant = [...(messages || [])]
    .reverse()
    .find((item) => item?.role === 'assistant' && String(item?.content || '').trim())
  if (latestAssistant) {
    recovered.push({
      id: `recovered-final-${latestAssistant.id}`,
      name: 'Final Output',
      timestamp: latestAssistant.timestamp,
      task: '',
      thinking: '',
      tools: [],
      response: latestAssistant.content || '',
    })
  }

  return recovered
}

const buildPreviewFromMessages = (messages) => {
  const latest = [...(messages || [])].reverse().find((item) => String(item?.content || '').trim())
  return latest?.content?.toString?.().replace(/\s+/g, ' ').slice(0, 120) || ''
}

const buildTaskSummary = (session, messages) => {
  if (!session?.currentTaskId) return []
  const latestUser = [...(messages || [])].reverse().find((item) => item?.role === 'user')
  return [
    {
      id: session.currentTaskId,
      title: (session.title || latestUser?.content || '任务').toString().slice(0, 60),
      description: latestUser?.content || '',
      agent: 'Task Coordinator',
      status: session.status === 'running' ? 'running' : 'completed',
      timestamp: toDate(session.updatedAt || session.createdAt),
    },
  ]
}

const mapServerConversation = (raw, localMeta, selectedTeamDefault, existingSession) => {
  const runtime = existingSession || createEmptyRuntimeState()
  return {
    id: raw?.conversation_id,
    conversationId: raw?.conversation_id,
    title: raw?.title || '新对话',
    createdAt: raw?.created_at || new Date().toISOString(),
    updatedAt: raw?.updated_at || raw?.created_at || new Date().toISOString(),
    preview: raw?.preview || existingSession?.preview || '',
    status: raw?.status || existingSession?.status || 'idle',
    selectedTeam: localMeta?.selectedTeam || raw?.latest_team || existingSession?.selectedTeam || selectedTeamDefault,
    currentTaskId: localMeta?.currentTaskId || raw?.latest_task_id || existingSession?.currentTaskId || null,
    latestTaskId: raw?.latest_task_id || existingSession?.latestTaskId || null,
    messageCount: Number(raw?.message_count || 0),
    messages: runtime.messages || [],
    tasks: runtime.tasks || [],
    workflowEvents: runtime.workflowEvents || [],
    agentMessages: runtime.agentMessages || [],
    activeTools: runtime.activeTools || [],
    selectedTool: runtime.selectedTool || null,
    loaded: Boolean(runtime.loaded),
  }
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${getApiBase()}${path}`, options)
  const text = await res.text()
  let json = null
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = null
  }
  if (!res.ok) {
    throw new Error(json?.detail || json?.message || `HTTP ${res.status}`)
  }
  return json
}

export function useSessionStore() {
  const sessions = ref([])
  const activeSessionId = ref(null)
  let uiCache = loadUiCache()

  const getSessionById = (id) => sessions.value.find((s) => s.id === id)

  const save = () => {
    uiCache = serializeUiCache(activeSessionId.value, sessions.value)
    saveUiCache(activeSessionId.value, sessions.value)
  }

  const mergeSessionsFromServer = (rows, selectedTeamDefault) => {
    const existingMap = new Map(sessions.value.map((session) => [session.id, session]))
    sessions.value = (rows || []).map((row) => {
      const localMeta = uiCache.sessionMeta?.[row?.conversation_id] || {}
      return mapServerConversation(row, localMeta, selectedTeamDefault, existingMap.get(row?.conversation_id))
    })
  }

  const refreshSessions = async (selectedTeamDefault = 'single_chain_team') => {
    const rows = await apiFetch('/api/v1/conversations?status=active&limit=200&offset=0')
    mergeSessionsFromServer(rows || [], selectedTeamDefault)
    if (activeSessionId.value && !getSessionById(activeSessionId.value)) {
      activeSessionId.value = sessions.value[0]?.id || null
    }
    save()
    return sessions.value
  }

  const syncSessionFromRefs = (refs) => {
    const session = getSessionById(activeSessionId.value)
    if (!session) return
    session.messages = [...(refs.messages.value || [])]
    session.tasks = [...(refs.tasks.value || [])]
    session.workflowEvents = [...(refs.workflowEvents.value || [])]
    session.agentMessages = [...(refs.agentMessages.value || [])]
    session.activeTools = [...(refs.activeTools.value || [])]
    session.selectedTool = refs.selectedTool.value || null
    session.selectedTeam = refs.selectedTeam.value || session.selectedTeam || 'single_chain_team'
    session.currentTaskId = refs.currentTaskId.value || session.currentTaskId || null
    session.latestTaskId = session.currentTaskId || session.latestTaskId || null
    session.status = refs.isAgentRunning.value ? 'running' : 'active'
    session.preview = buildPreviewFromMessages(session.messages) || session.preview
    session.loaded = true
    save()
  }

  const hydrateRefsFromSession = (refs, session) => {
    refs.messages.value = [...(session?.messages || [])]
    refs.tasks.value = [...(session?.tasks || [])]
    refs.workflowEvents.value = [...(session?.workflowEvents || [])]
    refs.agentMessages.value = [...(session?.agentMessages || [])]
    refs.activeTools.value = [...(session?.activeTools || [])]
    refs.selectedTool.value = session?.selectedTool || null
    refs.currentTaskId.value = session?.currentTaskId || null
    refs.selectedTeam.value = session?.selectedTeam || refs.selectedTeam.value
    refs.isAgentRunning.value = session?.status === 'running'
    refs.isLoading.value = false
  }

  const loadSessionData = async (sessionId) => {
    const session = getSessionById(sessionId)
    if (!session) return null

    const [info, messageRows] = await Promise.all([
      apiFetch(`/api/v1/conversations/${encodeURIComponent(sessionId)}`),
      apiFetch(`/api/v1/conversations/${encodeURIComponent(sessionId)}/messages?limit=500&offset=0`),
    ])

    const messages = (messageRows || []).map(mapConversationMessage)
    const latestTaskId =
      session.currentTaskId ||
      info?.latest_task_id ||
      session.latestTaskId ||
      [...messages]
        .reverse()
        .map((item) => item?.meta?.task_id)
        .find(Boolean) ||
      null

    let workflowEvents = []
    if (latestTaskId) {
      try {
        const workflow = await apiFetch(`/api/v1/tasks/${encodeURIComponent(latestTaskId)}/workflow?limit=2000&offset=0`)
        workflowEvents = (workflow?.data?.events || []).map(mapWorkflowEvent)
      } catch {
        workflowEvents = []
      }
    }

    session.title = info?.title || session.title || '新对话'
    session.createdAt = info?.created_at || session.createdAt
    session.updatedAt = info?.updated_at || session.updatedAt
    session.status = info?.status || session.status || 'active'
    session.currentTaskId = latestTaskId
    session.latestTaskId = latestTaskId
    session.messages = messages
    session.workflowEvents = workflowEvents
    session.agentMessages = buildRecoveredAgentMessages(workflowEvents, messages)
    session.activeTools = []
    session.selectedTool = null
    session.tasks = buildTaskSummary(session, messages)
    session.preview = buildPreviewFromMessages(messages) || session.preview
    session.loaded = true
    save()
    return session
  }

  const init = async (selectedTeamDefault = 'single_chain_team') => {
    uiCache = loadUiCache()
    activeSessionId.value = uiCache.activeSessionId
    await refreshSessions(selectedTeamDefault)
    if (!activeSessionId.value) {
      activeSessionId.value = sessions.value[0]?.id || null
    }
    save()
  }

  const createNewSession = async (refs) => {
    syncSessionFromRefs(refs)
    const created = await apiFetch('/api/v1/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: null }),
    })
    const id = created?.conversation_id
    if (!id) throw new Error('未返回 conversation_id')

    const session = mapServerConversation(
      {
        conversation_id: id,
        title: '新对话',
        status: 'active',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 0,
        preview: '',
        latest_task_id: null,
        latest_team: null,
      },
      { selectedTeam: refs.selectedTeam.value || 'single_chain_team', currentTaskId: null },
      refs.selectedTeam.value || 'single_chain_team',
      null,
    )
    sessions.value.unshift(session)
    activeSessionId.value = session.id
    hydrateRefsFromSession(refs, session)
    save()
    return session
  }

  const selectSession = async (refs, id) => {
    if (!id) return null
    if (id !== activeSessionId.value) {
      syncSessionFromRefs(refs)
    }
    activeSessionId.value = id
    let session = getSessionById(id)
    if (!session) {
      await refreshSessions(refs.selectedTeam.value || 'single_chain_team')
      session = getSessionById(id)
    }
    if (!session) return null
    session = await loadSessionData(id)
    hydrateRefsFromSession(refs, session)
    save()
    return session
  }

  const renameSession = async (id, title) => {
    const nextTitle = (title || '').trim().slice(0, 60)
    if (!nextTitle) return null
    const updated = await apiFetch(`/api/v1/conversations/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: nextTitle }),
    })
    const session = getSessionById(id)
    if (session) {
      session.title = updated?.title || nextTitle
      session.updatedAt = updated?.updated_at || session.updatedAt
    }
    save()
    return updated
  }

  const deleteSession = async (refs, id) => {
    await apiFetch(`/api/v1/conversations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
    const idx = sessions.value.findIndex((item) => item.id === id)
    if (idx >= 0) sessions.value.splice(idx, 1)
    if (activeSessionId.value === id) {
      const fallback = sessions.value[0] || null
      activeSessionId.value = fallback?.id || null
      if (fallback) {
        const loaded = await loadSessionData(fallback.id)
        hydrateRefsFromSession(refs, loaded)
      } else {
        refs.messages.value = []
        refs.tasks.value = []
        refs.workflowEvents.value = []
        refs.agentMessages.value = []
        refs.activeTools.value = []
        refs.selectedTool.value = null
        refs.currentTaskId.value = null
        refs.isAgentRunning.value = false
        refs.isLoading.value = false
      }
    }
    save()
  }

  return {
    sessions,
    activeSessionId,
    init,
    save,
    refreshSessions,
    getSessionById,
    createNewSession,
    selectSession,
    renameSession,
    deleteSession,
    syncSessionFromRefs,
    hydrateRefsFromSession,
    loadSessionData,
  }
}
