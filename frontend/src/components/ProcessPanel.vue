<template>
  <section class="panel-shell panel-shell--primary">
    <div class="panel-head">
      <div>
        <div class="panel-title">智能体过程</div>
        <div class="panel-subtitle">统一查看协作流程、思考片段、工具调用与输出。</div>
      </div>
      <div class="panel-meta">
        <span v-if="selectedTeam" class="panel-pill">{{ selectedTeam }}</span>
        <button
          type="button"
          class="panel-btn"
          :disabled="!currentTaskId"
          :title="currentTaskId ? `查看任务 ${currentTaskId} 的完整协作详情` : '当前没有可查看详情的任务'"
          @click="$emit('open-detail')"
        >
          查看详情
        </button>
      </div>
    </div>

    <div class="panel-scroll" :ref="setContainerRef">
      <div v-if="workflowEvents.length" class="workflow-list">
        <article
          v-for="event in workflowEvents"
          :key="event.id"
          class="workflow-item"
          :class="`workflow-item--${event.status}`"
        >
          <div class="workflow-rail">
            <span class="workflow-dot"></span>
          </div>
          <div class="workflow-copy">
            <div class="workflow-topline">
              <span class="workflow-agent">{{ event.agent }}</span>
              <span class="workflow-phase">{{ event.phase }}</span>
              <span class="workflow-time">{{ formatLogTime(event.timestamp) }}</span>
            </div>
            <p class="workflow-content">{{ event.content }}</p>
            <div v-if="workflowHandoffPayload(event)" class="workflow-json">
              <div class="workflow-json-title">handoff payload</div>
              <pre>{{ formatWorkflowJson(workflowHandoffPayload(event)) }}</pre>
            </div>
          </div>
        </article>
      </div>

      <div v-if="agentMessages.length" class="agent-stream">
        <article v-for="agent in agentMessages" :key="agent.id" class="agent-card">
          <div class="agent-card-top">
            <div class="agent-ident">
              <div>
                <div class="agent-name">{{ agent.name }}</div>
                <div class="agent-time">{{ formatLogTime(agent.timestamp) }}</div>
              </div>
            </div>
          </div>

          <div v-if="agent.task" class="agent-section">
            <div class="agent-section-label">Task</div>
            <div class="agent-section-body">{{ agent.task }}</div>
          </div>

          <div v-if="agent.thinking" class="agent-section">
            <div class="agent-section-label">Thinking</div>
            <div class="agent-section-body">{{ agent.thinking }}</div>
          </div>

          <div v-if="agent.tools?.length" class="agent-section">
            <div class="agent-section-label">Tools</div>
            <div class="agent-tool-list">
              <div v-for="tool in agent.tools" :key="tool.id" class="agent-tool-item">
                <div class="agent-tool-name">{{ tool.name }}</div>
                <code class="agent-tool-params">{{ tool.params }}</code>
              </div>
            </div>
          </div>

          <div v-if="agent.response" class="agent-section">
            <div class="agent-section-label">Output</div>
            <div class="agent-section-body agent-section-body--rich" v-html="formatResponse(agent.response)"></div>
          </div>
        </article>
      </div>

      <div v-if="!workflowEvents.length && !agentMessages.length" class="panel-empty">
        <div class="panel-empty-title">还没有过程数据</div>
        <p>发送一个任务后，这里会按时间顺序展示协作流和 Agent 输出。</p>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  workflowEvents: { type: Array, default: () => [] },
  agentMessages: { type: Array, default: () => [] },
  selectedTeam: { type: String, default: '' },
  currentTaskId: { type: String, default: null },
  formatLogTime: { type: Function, required: true },
  formatResponse: { type: Function, required: true },
  workflowHandoffPayload: { type: Function, required: true },
  formatWorkflowJson: { type: Function, required: true },
  setContainerRef: { type: Function, default: null },
})

defineEmits(['open-detail'])
</script>

<style scoped>
.panel-shell {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-3xl);
  background: var(--surface-elevated);
  box-shadow: var(--shadow-soft);
}

.panel-shell--primary {
  background: #ffffff;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 20px 22px 16px;
  border-bottom: 1px solid var(--border-subtle);
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.panel-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.panel-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.panel-pill,
.panel-btn {
  min-height: 32px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-muted);
}

.panel-btn {
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.16s ease, color 0.16s ease, border-color 0.16s ease, opacity 0.16s ease;
}

.panel-btn:not(:disabled):hover {
  background: #111111;
  border-color: #111111;
  color: #ffffff;
}

.panel-btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.panel-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px 18px 18px;
}

.workflow-list,
.agent-stream {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.agent-stream {
  margin-top: 14px;
}

.workflow-item,
.agent-card {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.72);
}

.workflow-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 12px;
  padding: 16px;
}

.workflow-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: var(--radius-pill);
  background: #111111;
  margin-top: 6px;
}

.workflow-item--error .workflow-dot {
  background: #8b4848;
}

.workflow-topline {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.workflow-agent,
.workflow-phase {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.workflow-phase {
  color: var(--text-secondary);
}

.workflow-time {
  color: var(--text-muted);
  font-size: 11px;
}

.workflow-content {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.workflow-json {
  margin-top: 12px;
  padding: 12px;
  border-radius: var(--radius-lg);
  background: rgba(17, 17, 17, 0.04);
}

.workflow-json-title,
.agent-section-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.workflow-json pre {
  margin-top: 8px;
  overflow: auto;
  font-family: var(--ui-font-mono);
  font-size: 12px;
  color: var(--text-primary);
}

.agent-card {
  padding: 18px;
}

.agent-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.agent-ident {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.agent-time {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.agent-section + .agent-section {
  margin-top: 14px;
}

.agent-section-body {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.agent-section-body--rich :deep(pre) {
  margin: 10px 0;
  padding: 12px;
  border-radius: var(--radius-lg);
  background: rgba(17, 17, 17, 0.05);
  overflow: auto;
  font-family: var(--ui-font-mono);
  font-size: 12px;
}

.agent-section-body--rich :deep(code) {
  font-family: var(--ui-font-mono);
}

.agent-tool-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.agent-tool-item {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(17, 17, 17, 0.04);
}

.agent-tool-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.agent-tool-params {
  display: block;
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  white-space: pre-wrap;
}

.panel-empty {
  padding: 52px 16px;
  text-align: center;
}

.panel-empty-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.panel-empty p {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
