<template>
  <div class="detail" :class="{ embedded: props.embedded }">
    <div class="header">
      <div class="left">
        <div class="title">协作详情</div>
        <div class="sub">task_id: <code>{{ taskId || '-' }}</code></div>
      </div>
      <div class="right">
        <button class="btn" :disabled="!taskId || !events.length" type="button" title="导出时间线为 Markdown" @click="exportTimelineMd">
          导出 MD
        </button>
        <button class="btn" :disabled="!taskId" @click="reload">刷新</button>
      </div>
    </div>

    <div v-if="!taskId" class="empty">
      请选择一个会话并开始运行任务后，再进入协作详情页查看回放与实时事件。
    </div>

    <div v-else class="workspace">
      <div class="summaryGrid">
        <div v-for="card in summaryCards" :key="card.label" class="summaryCard">
          <div class="summaryLabel">{{ card.label }}</div>
          <div class="summaryValue">{{ card.value }}</div>
          <div class="summaryMeta">{{ card.meta }}</div>
        </div>
      </div>

      <div class="grid">
        <div class="card timelineCard">
          <div class="cardHead">
            <div class="cardTitle">时间线（回放 + 实时）</div>
            <div class="small">共 {{ events.length }} 条事件，默认按序号和时间排序。</div>
          </div>

          <div class="timeline">
            <div v-for="ev in events" :key="ev.key" class="item" :class="ev.data?.status">
              <div class="meta">
                <span class="seq">#{{ ev.data?.seq ?? 0 }}</span>
                <span class="agent">{{ ev.data?.agent }}</span>
                <span class="phase">{{ ev.data?.phase }}</span>
                <span class="ts">{{ fmt(ev.timestamp) }}</span>
              </div>
              <div class="content">{{ ev.data?.content }}</div>
              <div v-if="ev.data?.meta?.handoff_summary" class="subtask">交接摘要：{{ ev.data.meta.handoff_summary }}</div>
              <div v-if="ev.data?.meta?.sub_task" class="subtask">子任务：{{ ev.data.meta.sub_task }}</div>
              <div v-if="handoffPayloadOf(ev.data)" class="handoffJson">
                <div class="handoffJsonTitle">交接 JSON</div>
                <pre class="handoffJsonCode">{{ prettyJson(handoffPayloadOf(ev.data)) }}</pre>
              </div>
            </div>
          </div>
        </div>

        <div class="sideStack">
          <div class="card focusCard">
            <div class="cardHead">
              <div class="cardTitle">任务透视</div>
              <div class="small">把当前任务、最新状态和口径说明收在一起。</div>
            </div>

            <div class="focusList">
              <div v-for="item in focusItems" :key="item.label" class="focusItem">
                <div class="focusLabel">{{ item.label }}</div>
                <div class="focusValue">{{ item.value }}</div>
              </div>
            </div>

            <div class="hintBox">
              <div class="hintTitle">指标口径</div>
              <div class="hintLine"><code>total_events</code>：落库的 <code>workflow_event</code> 总数。</div>
              <div class="hintLine"><code>agent_turns</code>：来自 <code>agent_started</code> 的处理轮次。</div>
              <div class="hintLine"><code>tool_event_count</code>：工具决策与执行相关事件的聚合值。</div>
              <div class="hintLine"><code>error_count</code>：该 Agent 相关事件里 <code>status=error</code> 的数量。</div>
            </div>

            <div class="seqRules">
              <div class="seqRulesTitle">序号命名规则（时间线 <code>#数字</code>）</div>
              <div class="seqRule"><code>#1</code><span>任务开始（<code>task_started</code>）</span></div>
              <div class="seqRule"><code>#3</code><span>记忆预检（<code>memory_precheck</code>）</span></div>
              <div class="seqRule"><code>#100+</code><span>Agent/工具执行过程（<code>agent_started</code>、<code>tool_decided</code>、<code>tool_finished</code> 等）</span></div>
              <div class="seqRule"><code>#9999</code><span>助手消息落盘回放（<code>message</code>）</span></div>
              <div class="seqRule"><code>#10000</code><span>任务结束（<code>task_finished</code>）</span></div>
              <div class="seqRule"><code>排序规则</code><span>先按 <code>seq</code> 升序；若相同，再按时间戳升序</span></div>
            </div>
          </div>

          <div class="card graphCard">
            <div class="cardHead">
              <div class="cardTitle">协作图</div>
              <div class="small">点击一条边可查看该交接的子任务样例。</div>
            </div>

            <div v-if="graph" class="graphWrap">
              <div class="graphTop">
                <div class="legend">
                  <span class="dot"></span> Agent 节点
                  <span class="arrow">→</span> 相邻子任务交接（基于 <code>agent_started</code> 顺序推断）
                </div>
              </div>

              <div class="nodesRow">
                <div v-for="n in graph.nodes" :key="n.id" class="node">{{ n.id }}</div>
              </div>

              <div v-if="graph.edges?.length" class="edges">
                <button
                  v-for="e in graph.edges"
                  :key="edgeKey(e)"
                  class="edgeBtn"
                  :class="{ active: selectedEdgeKey === edgeKey(e) }"
                  @click="selectEdge(e)"
                  title="点击查看协作细节"
                >
                  <span class="from">{{ e.source }}</span>
                  <span class="arr">→</span>
                  <span class="to">{{ e.target }}</span>
                  <span class="count">×{{ e.count }}</span>
                </button>
              </div>
              <div v-else class="emptySmall">该任务还没有足够的 agent_started 事件来推断协作边</div>

              <div v-if="selectedEdge" class="edgeDetail">
                <div class="edgeTitle">协作细节：{{ selectedEdge.source }} → {{ selectedEdge.target }}</div>
                <div v-if="selectedEdge.samples?.length" class="samples">
                  <div v-for="s in selectedEdge.samples" :key="s" class="sample">- {{ s }}</div>
                </div>
                <div v-else class="emptySmall">暂无子任务样例（需要后端在 agent_started.meta.sub_task 填充）</div>
              </div>
            </div>
            <div v-else class="emptySmall">暂无协作图</div>
          </div>

          <div class="card metricsCard">
            <div class="cardHead">
              <div class="cardTitle">Agent 指标</div>
              <div class="small">按 Agent 聚合事件数、回合数、工具事件和错误数量。</div>
            </div>

            <div v-if="metrics" class="metrics">
              <div class="kpiRow">
                <div class="kpi"><div class="k">任务事件数</div><div class="v">{{ metrics.total_events }}</div></div>
                <div class="kpi"><div class="k">Agent 数</div><div class="v">{{ metricsAgents.length }}</div></div>
              </div>
              <div class="table">
                <div class="tr head">
                  <div>Agent</div>
                  <div>事件数</div>
                  <div>回合数</div>
                  <div>工具事件</div>
                  <div>错误</div>
                </div>
                <div v-for="a in metricsAgents" :key="a.agent" class="tr">
                  <div class="agentCell">{{ a.agent }}</div>
                  <div>{{ a.event_count }}</div>
                  <div>{{ a.agent_turns }}</div>
                  <div>{{ a.tool_event_count }}</div>
                  <div :class="{ bad: a.error_count > 0 }">{{ a.error_count }}</div>
                </div>
              </div>
            </div>
            <div v-else class="emptySmall">暂无指标</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getApiBase } from '../composables/useApiBase'
import { useTaskStream } from '../composables/useTaskStream'

const props = defineProps({
  taskId: { type: String, default: null },
  embedded: { type: Boolean, default: false },
})

const events = ref([])
const metrics = ref(null)
const graph = ref(null)
const selectedEdge = ref(null)
const selectedEdgeKey = ref(null)

const { wsStatus, connectTaskStreamSocket } = useTaskStream()
let streamWs = null

const keyOf = (ev) => `${ev.task_id || ''}-${ev.timestamp || ''}-${ev.data?.seq ?? 0}-${ev.data?.agent || ''}-${ev.data?.phase || ''}`
const isPlainObject = (value) => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const handoffPayloadOf = (data) => {
  const payload = data?.meta?.handoff_payload
  return isPlainObject(payload) && Object.keys(payload).length > 0 ? payload : null
}
const prettyJson = (value) => {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value ?? '')
  }
}

const mergeEvents = (incoming) => {
  const map = new Map(events.value.map((e) => [e.key, e]))
  for (const e of incoming) map.set(e.key, e)
  events.value = Array.from(map.values()).sort((a, b) => (a.data?.seq ?? 0) - (b.data?.seq ?? 0) || new Date(a.timestamp) - new Date(b.timestamp))
}

const loadWorkflow = async () => {
  const base = getApiBase()
  const res = await fetch(`${base}/api/v1/tasks/${encodeURIComponent(props.taskId)}/workflow?limit=2000&offset=0`)
  const json = await res.json()
  const list = (json?.data?.events || []).map((e) => ({ ...e, key: keyOf(e) }))
  mergeEvents(list)
}

const loadGraph = async () => {
  const base = getApiBase()
  const res = await fetch(`${base}/api/v1/tasks/${encodeURIComponent(props.taskId)}/graph`)
  const json = await res.json()
  graph.value = json?.data || null
  selectedEdge.value = null
  selectedEdgeKey.value = null
}

const loadMetrics = async () => {
  const base = getApiBase()
  const res = await fetch(`${base}/api/v1/tasks/${encodeURIComponent(props.taskId)}/metrics`)
  const json = await res.json()
  metrics.value = json?.data || null
}

const connectStream = () => {
  try {
    streamWs?.close()
  } catch {
    // ignore
  }
  if (!props.taskId) return
  streamWs = connectTaskStreamSocket(props.taskId, (msg) => {
    if (msg?.event !== 'workflow_event') return
    const ev = { task_id: msg.task_id, timestamp: msg.timestamp, data: msg.data, key: keyOf({ task_id: msg.task_id, timestamp: msg.timestamp, data: msg.data }) }
    mergeEvents([ev])
  })
}

const reload = async () => {
  if (!props.taskId) return
  events.value = []
  await Promise.all([loadWorkflow(), loadGraph(), loadMetrics()])
  connectStream()
}

const edgeKey = (e) => `${e.source}-->${e.target}`
const selectEdge = (e) => {
  selectedEdge.value = e
  selectedEdgeKey.value = edgeKey(e)
}

const fmt = (ts) => {
  try {
    return new Date(ts).toLocaleString('zh-CN')
  } catch {
    return ts || ''
  }
}

const formatWsStatus = (status) => {
  if (status === 'connected') return '已连接'
  if (status === 'connecting') return '连接中'
  if (status === 'disconnected') return '已断开'
  return status || '-'
}

const metricsAgents = computed(() => (Array.isArray(metrics.value?.agents) ? metrics.value.agents : []))
const latestEvent = computed(() => (events.value.length ? events.value[events.value.length - 1] : null))
const errorAgentCount = computed(() => metricsAgents.value.filter((agent) => Number(agent?.error_count || 0) > 0).length)

const summaryCards = computed(() => [
  {
    label: '任务事件',
    value: metrics.value?.total_events ?? events.value.length,
    meta: '已落库的 workflow_event 数量',
  },
  {
    label: '参与 Agent',
    value: metricsAgents.value.length,
    meta: errorAgentCount.value ? `${errorAgentCount.value} 个存在错误记录` : '当前没有错误 Agent',
  },
  {
    label: '协作边',
    value: graph.value?.edges?.length || 0,
    meta: selectedEdge.value ? `${selectedEdge.value.source} → ${selectedEdge.value.target}` : '点击右侧边查看交接样例',
  },
  {
    label: '最近事件',
    value: latestEvent.value?.data?.phase || '-',
    meta: latestEvent.value ? `${latestEvent.value.data?.agent || 'system'} · ${fmt(latestEvent.value.timestamp)}` : '等待任务产生事件',
  },
])

const focusItems = computed(() => [
  {
    label: '任务 ID',
    value: props.taskId || '-',
  },
  {
    label: '实时连接',
    value: formatWsStatus(wsStatus.value),
  },
  {
    label: '最新 Agent',
    value: latestEvent.value?.data?.agent || '-',
  },
  {
    label: '当前交接',
    value: selectedEdge.value ? `${selectedEdge.value.source} → ${selectedEdge.value.target}` : '未选择',
  },
])

const exportTimelineMd = () => {
  if (!props.taskId || !events.value.length) return
  const lines = [
    '# AgentMesh 任务时间线导出',
    '',
    `- task_id: \`${props.taskId}\``,
    `- 导出时间: ${fmt(new Date())}`,
    '',
    '## 事件列表',
    '',
  ]
  for (const ev of events.value) {
    const d = ev.data || {}
    const handoffPayload = handoffPayloadOf(d)
    lines.push(`### #${d.seq ?? 0} · ${d.agent ?? ''} · \`${d.phase ?? ''}\``)
    lines.push('')
    lines.push(`- 时间：${fmt(ev.timestamp)}`)
    lines.push(`- 状态：${d.status ?? ''}`)
    lines.push(`- 内容：${d.content ?? ''}`)
    if (d.meta?.sub_task) {
      lines.push(`- 子任务：${d.meta.sub_task}`)
    }
    if (handoffPayload) {
      lines.push('- 交接 JSON：')
      lines.push('```json')
      lines.push(prettyJson(handoffPayload))
      lines.push('```')
    }
    lines.push('')
  }
  const md = lines.join('\n')
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `agentmesh-task-${props.taskId}-timeline.md`
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  if (!props.taskId) return
  await reload()
})

watch(
  () => props.taskId,
  async (next) => {
    if (!next) {
      connectStream()
      events.value = []
      metrics.value = null
      graph.value = null
      selectedEdge.value = null
      selectedEdgeKey.value = null
      return
    }
    await reload()
  }
)

onBeforeUnmount(() => {
  try {
    streamWs?.close()
  } catch {
    // ignore
  }
})
</script>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #ffffff;
}

.detail.embedded {
  background: transparent;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: #ffffff;
}

.detail.embedded .header {
  margin: 12px 12px 0;
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(16px);
}

.title {
  font-weight: 700;
  color: #111827;
}
.sub {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}
.right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pill {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.8);
}
.pill.connected {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.12);
  color: #065f46;
}
.pill.connecting {
  border-color: rgba(234, 179, 8, 0.35);
  background: rgba(234, 179, 8, 0.12);
  color: #92400e;
}
.pill.disconnected {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.12);
  color: #991b1b;
}
.btn {
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: white;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.empty {
  padding: 18px 16px;
  color: #6b7280;
}

.workspace {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
  padding: 12px;
}

.summaryGrid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summaryCard {
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 18px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 14px 28px rgba(18, 22, 28, 0.05);
}

.summaryLabel {
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #7a8490;
  font-weight: 800;
}

.summaryValue {
  margin-top: 8px;
  font-size: 24px;
  line-height: 1;
  font-weight: 800;
  color: #232830;
}

.summaryMeta {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.55;
  color: #68717d;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(340px, 0.88fr);
  gap: 12px;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.sideStack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.card {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 18px;
  padding: 14px;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.cardHead {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.timelineCard {
  overflow-y: auto;
  overflow-x: hidden;
}

.focusCard,
.metricsCard,
.graphCard {
  overflow-y: auto;
  overflow-x: hidden;
  height: auto;
}

.cardTitle {
  font-size: 12px;
  font-weight: 700;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 0 0 auto;
  min-height: 0;
  overflow: visible;
  padding-right: 0;
}
.item {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  padding: 10px;
  background: rgba(249, 250, 251, 0.7);
}
.item.ok {
  border-color: rgba(16, 185, 129, 0.25);
}
.item.error {
  border-color: rgba(239, 68, 68, 0.25);
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 6px;
}
.seq {
  font-weight: 700;
  color: #111827;
}
.agent {
  font-weight: 700;
  color: #1e40af;
}
.phase {
  font-weight: 600;
  color: #374151;
}
.ts {
  margin-left: auto;
  opacity: 0.8;
}
.content {
  font-size: 12px;
  color: #374151;
  line-height: 1.5;
  word-break: break-word;
}

.subtask {
  margin-top: 6px;
  font-size: 12px;
  color: #1f2937;
  background: rgba(51, 112, 255, 0.08);
  border: 1px solid rgba(51, 112, 255, 0.18);
  border-radius: 10px;
  padding: 8px 10px;
}
.handoffJson {
  margin-top: 8px;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.04);
}
.handoffJsonTitle {
  font-size: 11px;
  font-weight: 800;
  color: #334155;
  padding: 8px 10px 0;
}
.handoffJsonCode {
  margin: 0;
  padding: 8px 10px 10px;
  font-size: 11px;
  line-height: 1.45;
  color: #0f172a;
  overflow: auto;
  max-height: 240px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.focusList {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.focusItem {
  border: 1px solid rgba(27, 31, 38, 0.08);
  border-radius: 14px;
  padding: 11px 12px;
  background: rgba(249, 250, 251, 0.72);
}

.focusLabel {
  font-size: 11px;
  color: #7a8490;
  margin-bottom: 6px;
}

.focusValue {
  font-size: 13px;
  line-height: 1.5;
  font-weight: 700;
  color: #232830;
  word-break: break-word;
}

.hintBox {
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  padding: 12px;
  margin-bottom: 12px;
}

.hintTitle {
  font-size: 12px;
  font-weight: 800;
  color: #232830;
  margin-bottom: 8px;
}

.hintLine {
  font-size: 12px;
  line-height: 1.65;
  color: #68717d;
}

.hintLine + .hintLine {
  margin-top: 6px;
}

.seqRules {
  border: 1px solid rgba(51, 112, 255, 0.2);
  background: rgba(51, 112, 255, 0.05);
  border-radius: 12px;
  padding: 10px;
  display: grid;
  gap: 6px;
}
.seqRulesTitle {
  font-size: 12px;
  font-weight: 800;
  color: #1e40af;
}
.seqRule {
  display: grid;
  grid-template-columns: minmax(78px, auto) 1fr;
  gap: 8px;
  align-items: start;
  font-size: 12px;
  color: #374151;
}
.seqRule code {
  font-weight: 700;
}
.metrics .kpiRow {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}
.kpi {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  padding: 10px;
  background: rgba(249, 250, 251, 0.7);
}
.kpi .k {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}
.kpi .v {
  font-size: 18px;
  font-weight: 800;
  color: #111827;
}
.table {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  overflow: hidden;
}
.tr {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 0.8fr 0.9fr 0.7fr;
  gap: 0;
}
.tr > div {
  padding: 10px;
  font-size: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  color: #374151;
}
.tr.head > div {
  font-size: 11px;
  font-weight: 800;
  color: #111827;
  background: rgba(0, 0, 0, 0.04);
  border-top: none;
}
.agentCell {
  font-weight: 800;
  color: #1e40af;
}
.bad {
  color: #991b1b;
  font-weight: 800;
}

.graphWrap {
  display: grid;
  gap: 10px;
}
.graphTop {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.legend {
  font-size: 12px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 8px;
}
.legend .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3370ff;
  box-shadow: 0 0 0 4px rgba(51, 112, 255, 0.18);
}
.legend .arrow {
  font-weight: 900;
  color: #111827;
}
.small {
  font-size: 11px;
  color: #9ca3af;
}
.nodesRow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.node {
  border: 1px solid rgba(51, 112, 255, 0.18);
  background: rgba(51, 112, 255, 0.06);
  color: #1e40af;
  font-weight: 900;
  font-size: 12px;
  padding: 8px 10px;
  border-radius: 999px;
}
.edges {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.edgeBtn {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(249, 250, 251, 0.7);
  border-radius: 12px;
  padding: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #374151;
  text-align: left;
}
.edgeBtn:hover {
  border-color: rgba(51, 112, 255, 0.35);
  background: rgba(51, 112, 255, 0.08);
}
.edgeBtn.active {
  border-color: rgba(51, 112, 255, 0.55);
  box-shadow: 0 0 0 3px rgba(51, 112, 255, 0.12);
}
.edgeBtn .from,
.edgeBtn .to {
  font-weight: 900;
  color: #1e40af;
}
.edgeBtn .arr {
  color: #111827;
  font-weight: 900;
}
.edgeBtn .count {
  margin-left: auto;
  font-weight: 900;
  color: #111827;
}
.edgeDetail {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  padding: 10px;
}
.edgeTitle {
  font-weight: 900;
  color: #111827;
  margin-bottom: 8px;
  font-size: 12px;
}
.samples {
  display: grid;
  gap: 6px;
}
.sample {
  font-size: 12px;
  color: #374151;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 10px;
  padding: 8px 10px;
}
.emptySmall {
  font-size: 12px;
  color: #9ca3af;
}

/* Neutral office-workbench overrides */
.title,
.cardTitle,
.summaryValue,
.seq,
.edgeTitle {
  color: #232830;
}

.sub,
.summaryMeta,
.seqRules,
.seqRule,
.small,
.emptySmall,
.empty,
.meta {
  color: #68717d;
}

.seqRulesTitle,
.agent,
.edgeBtn .from,
.edgeBtn .to,
.agentCell {
  color: #485b74;
}

.card,
.item,
.kpi,
.table,
.edgeBtn,
.edgeDetail,
.sample,
.handoffJson,
.seqRules {
  border-color: rgba(27, 31, 38, 0.1);
  background: #ffffff;
  box-shadow: 0 12px 24px rgba(18, 22, 28, 0.05);
}

.phase,
.content,
.sample {
  color: #37404b;
}

.pill {
  border-color: rgba(27, 31, 38, 0.08);
  background: rgba(255, 255, 255, 0.7);
  color: #4f5865;
}

.btn {
  border-color: rgba(27, 31, 38, 0.12);
  background: rgba(255, 255, 255, 0.84);
  color: #2b333d;
}

.btn:hover:not(:disabled) {
  border-color: rgba(27, 31, 38, 0.16);
  background: rgba(255, 255, 255, 0.96);
}

.node,
.subtask {
  border-color: rgba(27, 31, 38, 0.1);
  background: #ffffff;
  color: #37404b;
}

.legend .dot {
  background: #52657f;
  box-shadow: 0 0 0 4px rgba(82, 101, 127, 0.14);
}

.edgeBtn:hover {
  border-color: rgba(27, 31, 38, 0.16);
  background: rgba(255, 255, 255, 0.92);
}

.workspace {
  animation: detail-appear 0.42s ease both;
}

@keyframes detail-appear {
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
  .summaryGrid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .grid {
    grid-template-columns: 1fr;
    overflow: visible;
  }

  .sideStack {
    overflow: visible;
    padding-right: 0;
  }
}

@media (max-width: 720px) {
  .summaryGrid,
  .focusList,
  .metrics .kpiRow {
    grid-template-columns: 1fr;
  }

  .header,
  .detail.embedded .header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
