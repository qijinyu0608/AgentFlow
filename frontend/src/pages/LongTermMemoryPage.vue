<template>
  <div class="mem">
    <div class="top">
      <div class="topMain">
        <div class="title">长期记忆（MEMORY.md）</div>
        <div class="topHint">把稳定的身份信息、偏好、长期约束和协作方式沉淀下来，后续任务会更贴近你的习惯。</div>
      </div>
      <div class="meta">
        <span v-if="isDirty" class="pill pillWarn">有未保存修改</span>
        <span v-if="filePath" class="pill">文件：<code>{{ filePath }}</code></span>
        <span v-if="workspaceRoot" class="pill">workspace：<code>{{ workspaceRoot }}</code></span>
        <span v-if="updatedAt" class="pill">updated_at：<code>{{ updatedAt }}</code></span>
      </div>
    </div>

    <div v-if="notice" class="notice" :class="notice.type">{{ notice.text }}</div>

    <div v-if="loading" class="loading">加载中…</div>

    <div v-else class="grid">
      <div class="card">
        <div class="cardHeader">
          <div>
            <div class="cardTitle">基本信息</div>
            <div class="cardSubtitle">结构化信息适合放这里，方便后续工具和模型稳定读取。</div>
          </div>
        </div>

        <div class="form">
          <div class="row">
            <label>姓名/昵称</label>
            <input v-model="form.name" placeholder="例如：小明" />
          </div>
          <div class="row">
            <label>角色/职能</label>
            <input v-model="form.role" placeholder="例如：产品/研发/分析" />
          </div>
          <div class="row">
            <label>组织/团队</label>
            <input v-model="form.organization" placeholder="例如：XX公司/XX团队" />
          </div>
          <div class="row">
            <label>联系方式</label>
            <input v-model="form.contact" placeholder="邮箱/微信/电话等" />
          </div>
          <div class="row2">
            <div class="row">
              <label>时区</label>
              <input v-model="form.timezone" placeholder="例如：Asia/Shanghai" />
            </div>
            <div class="row">
              <label>语言</label>
              <input v-model="form.language" placeholder="例如：zh-CN" />
            </div>
          </div>
          <div class="row">
            <label>偏好</label>
            <textarea v-model="form.preferences" rows="5" placeholder="例如：回答更简洁；偏好 TypeScript；优先给出可复制命令…" />
          </div>
          <div class="row">
            <label>标签（逗号分隔）</label>
            <input v-model="tagsText" placeholder="例如：backend, vue, agent" />
          </div>

          <div class="custom">
            <div class="customHead">
              <div class="customTitle">自定义键值对</div>
              <button type="button" class="btn" @click="addCustomRow">新增一行</button>
            </div>
            <div class="customHint">适合放你自己的分类字段，例如工作流、项目、输出格式等。</div>
            <div v-if="customRows.length === 0" class="emptySmall">暂无自定义项</div>
            <div v-else class="kvList">
              <div v-for="(r, idx) in customRows" :key="idx" class="kvRow">
                <input v-model="r.key" placeholder="key" />
                <input v-model="r.value" placeholder="value" />
                <button type="button" class="iconBtn danger" title="删除" @click="removeCustomRow(idx)">删除</button>
              </div>
            </div>
          </div>
        </div>

        <div class="actions">
          <button class="primary" :disabled="saving" @click="save(false)">
            {{ saving ? '保存中…' : '保存' }}
          </button>
          <button class="btn" :disabled="saving" @click="save(true)">保存并重建索引</button>
          <button class="btn" :disabled="loading || saving" @click="load">刷新</button>
        </div>
      </div>

      <div class="card">
        <div class="cardHeader">
          <div>
            <div class="cardTitle">正文（YAML 头部由系统维护）</div>
            <div class="cardSubtitle">这里适合写长期背景、协作规则、默认上下文、常用术语和历史决策。</div>
          </div>
        </div>
        <textarea v-model="content" class="editor" rows="28" placeholder="在这里编辑长期记忆正文…" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { getApiBase } from '../composables/useApiBase'

const loading = ref(false)
const saving = ref(false)
const notice = ref(null) // {type:'ok'|'error'|'info', text:string}

const workspaceRoot = ref('')
const filePath = ref('')
const updatedAt = ref('')

const form = ref({
  name: '',
  role: '',
  organization: '',
  contact: '',
  timezone: '',
  language: '',
  preferences: '',
})

const tagsText = ref('')
const content = ref('')
const customRows = ref([]) // [{key,value}]
const initialSnapshot = ref('')

const tags = computed(() => {
  const raw = (tagsText.value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  return Array.from(new Set(raw))
})

const customMap = computed(() => {
  const out = {}
  for (const r of customRows.value) {
    const k = (r.key || '').trim()
    if (!k) continue
    out[k] = String(r.value ?? '').trim()
  }
  return out
})

const buildSnapshot = () =>
  JSON.stringify({
    form: form.value,
    tags: tags.value,
    content: content.value,
    custom: customMap.value,
  })

const isDirty = computed(() => buildSnapshot() !== initialSnapshot.value)

const syncSnapshot = () => {
  initialSnapshot.value = buildSnapshot()
}

const addCustomRow = () => {
  customRows.value.push({ key: '', value: '' })
}

const removeCustomRow = (idx) => {
  customRows.value.splice(idx, 1)
}

const setNotice = (type, text) => {
  notice.value = { type, text }
  window.setTimeout(() => {
    if (notice.value?.text === text) notice.value = null
  }, 3500)
}

const load = async () => {
  loading.value = true
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/memory/long-term`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = await res.json()

    workspaceRoot.value = json?.workspace_root || ''
    filePath.value = json?.path || ''
    updatedAt.value = json?.updated_at || ''

    const meta = json?.meta || {}
    form.value = {
      name: meta?.name || '',
      role: meta?.role || '',
      organization: meta?.organization || '',
      contact: meta?.contact || '',
      timezone: meta?.timezone || '',
      language: meta?.language || '',
      preferences: meta?.preferences || '',
    }
    const t = meta?.tags
    tagsText.value = Array.isArray(t) ? t.join(', ') : (t || '')
    content.value = json?.content || ''

    const c = meta?.custom
    if (c && typeof c === 'object' && !Array.isArray(c)) {
      customRows.value = Object.entries(c).map(([k, v]) => ({ key: k, value: String(v ?? '') }))
    } else {
      customRows.value = []
    }

    syncSnapshot()
    setNotice('ok', '已加载')
  } catch (e) {
    setNotice('error', `加载失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

const save = async (reindex) => {
  saving.value = true
  try {
    const base = getApiBase()
    const meta = {
      ...form.value,
      tags: tags.value,
      custom: customMap.value,
    }
    const res = await fetch(`${base}/api/v1/memory/long-term?reindex=${reindex ? 'true' : 'false'}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meta, content: content.value }),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) {
      const d = json?.detail || json?.message || `HTTP ${res.status}`
      throw new Error(d)
    }

    updatedAt.value = json?.updated_at || updatedAt.value
    syncSnapshot()
    setNotice('ok', reindex ? '已保存并重建当前长期记忆索引' : '已保存')
  } catch (e) {
    setNotice('error', `保存失败：${e?.message || e}`)
  } finally {
    saving.value = false
  }
}

const confirmDiscardIfNeeded = () => {
  if (!isDirty.value) return true
  return window.confirm('长期记忆有未保存修改，确定离开并放弃这些改动吗？')
}

const handleBeforeUnload = (event) => {
  if (!isDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

window.addEventListener('beforeunload', handleBeforeUnload)

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

defineExpose({
  load,
  isDirty,
  confirmDiscardIfNeeded,
})

load()
</script>

<style scoped>
.mem {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.6);
}
.topMain {
  display: grid;
  gap: 4px;
}
.title {
  font-weight: 800;
  color: #111827;
}
.topHint {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
  max-width: 680px;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}
.pill {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.8);
  color: #374151;
}
.pillWarn {
  border-color: rgba(245, 158, 11, 0.35);
  background: rgba(245, 158, 11, 0.12);
  color: #92400e;
}
.notice {
  margin: 10px 12px 0;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  color: #374151;
}
.notice.ok {
  border-color: rgba(16, 185, 129, 0.25);
  background: rgba(16, 185, 129, 0.08);
}
.notice.error {
  border-color: rgba(239, 68, 68, 0.25);
  background: rgba(239, 68, 68, 0.08);
}
.notice.info {
  border-color: rgba(59, 130, 246, 0.25);
  background: rgba(59, 130, 246, 0.08);
}
.loading {
  padding: 18px 16px;
  color: #6b7280;
}
.grid {
  display: grid;
  grid-template-columns: 0.95fr 1.05fr;
  gap: 12px;
  padding: 12px;
  overflow: auto;
  min-height: 0;
  flex: 1;
}
.card {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  padding: 12px;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.cardHeader {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.cardTitle {
  font-size: 12px;
  font-weight: 800;
  color: #374151;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.cardSubtitle {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
}
.form {
  display: grid;
  gap: 10px;
}
.row {
  display: grid;
  gap: 6px;
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
label {
  font-size: 12px;
  font-weight: 700;
  color: #374151;
}
input,
textarea {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  padding: 10px 10px;
  font-size: 13px;
  outline: none;
  background: white;
  color: #111827;
}
textarea {
  resize: vertical;
}
input:focus,
textarea:focus {
  border-color: rgba(51, 112, 255, 0.6);
  box-shadow: 0 0 0 3px rgba(51, 112, 255, 0.12);
}
.custom {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  padding-top: 10px;
}
.customHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}
.customTitle {
  font-weight: 800;
  font-size: 12px;
  color: #111827;
}
.customHint {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}
.kvList {
  display: grid;
  gap: 8px;
}
.kvRow {
  display: grid;
  grid-template-columns: 0.9fr 1.1fr auto;
  gap: 8px;
  align-items: center;
}
.kvRow input {
  padding: 8px 10px;
}
.iconBtn {
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: white;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #374151;
}
.iconBtn.danger:hover {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.08);
  color: #991b1b;
}
.btn {
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: white;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #374151;
}
.btn:hover {
  border-color: rgba(51, 112, 255, 0.35);
  background: rgba(51, 112, 255, 0.08);
  color: #1e40af;
}
.primary {
  border: none;
  background: linear-gradient(135deg, #3370ff 0%, #1e40af 100%);
  color: white;
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 12px;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(51, 112, 255, 0.35);
}
.primary:disabled,
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.editor {
  flex: 1;
  min-height: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
}
.emptySmall {
  font-size: 12px;
  color: #9ca3af;
}

/* Neutral office-workbench overrides */
.mem {
  background: #ffffff;
}

.top {
  border-bottom-color: rgba(27, 31, 38, 0.08);
  background: #ffffff;
}

.title {
  color: #232830;
}

.topHint,
.cardSubtitle,
.customHint,
.emptySmall {
  color: #68717d;
}

.pill {
  border-color: rgba(27, 31, 38, 0.08);
  background: rgba(255, 255, 255, 0.7);
  color: #4f5865;
}

.notice,
.card {
  border-color: rgba(27, 31, 38, 0.1);
  background: #ffffff;
  box-shadow: 0 12px 24px rgba(18, 22, 28, 0.05);
}

.cardTitle,
.customTitle,
label {
  color: #232830;
}

input,
textarea {
  border-color: rgba(27, 31, 38, 0.12);
  background: rgba(255, 255, 255, 0.98);
  color: #2b333d;
}

input:focus,
textarea:focus {
  border-color: rgba(27, 31, 38, 0.22);
  box-shadow: 0 0 0 3px rgba(18, 22, 28, 0.08);
}

.btn,
.iconBtn {
  border-color: rgba(27, 31, 38, 0.12);
  background: rgba(255, 255, 255, 0.86);
  color: #2b333d;
}

.btn:hover {
  border-color: rgba(27, 31, 38, 0.16);
  background: rgba(255, 255, 255, 0.96);
}

.primary {
  background: #111111;
  box-shadow: 0 10px 22px rgba(17, 17, 17, 0.22);
}

.editor {
  background: rgba(252, 254, 255, 0.98);
}

.grid {
  animation: mem-appear 0.42s ease both;
}

@keyframes mem-appear {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 992px) {
  .grid {
    grid-template-columns: 1fr;
  }
  .top {
    flex-direction: column;
  }
  .meta {
    justify-content: flex-start;
  }
}
</style>
