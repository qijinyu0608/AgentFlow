<template>
  <section class="panel-shell">
    <div class="panel-head">
      <div>
        <div class="panel-title">工具结果</div>
        <div class="panel-subtitle">查看最近的工具调用输入与输出。</div>
      </div>
    </div>

    <div v-if="activeTools.length" class="tool-tabs">
      <button
        v-for="tool in activeTools"
        :key="tool.id"
        type="button"
        class="tool-tab"
        :class="{ active: selectedTool === tool.id }"
        @click="$emit('update:selectedTool', tool.id)"
      >
        <span class="tool-tab-name">{{ tool.name }}</span>
      </button>
    </div>

    <div class="tool-body">
      <div v-if="selectedToolData" class="tool-card">
        <template v-if="selectedToolData.type === 'search'">
          <div class="tool-label">Search</div>
          <div class="tool-query">查询：{{ selectedToolData.query }}</div>
          <div class="tool-search-list">
            <article v-for="item in selectedToolData.results" :key="item.id" class="tool-search-item">
              <h4>{{ item.title }}</h4>
              <p>{{ item.snippet }}</p>
              <a :href="item.url" target="_blank" rel="noreferrer">{{ item.url }}</a>
            </article>
          </div>
        </template>

        <template v-else-if="selectedToolData.type === 'file'">
          <div class="tool-label">File</div>
          <div class="tool-query">{{ selectedToolData.path }}</div>
          <pre class="tool-pre">{{ selectedToolData.content }}</pre>
        </template>

        <template v-else>
          <div class="tool-label">Terminal</div>
          <div class="tool-query">$ {{ selectedToolData.command }}</div>
          <pre class="tool-pre">{{ selectedToolData.output }}</pre>
        </template>
      </div>

      <div v-else class="panel-empty">
        <div class="panel-empty-title">等待工具输出</div>
        <p>当 Agent 触发工具后，这里会同步展示执行结果。</p>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  activeTools: { type: Array, default: () => [] },
  selectedTool: { type: String, default: null },
  selectedToolData: { type: Object, default: null },
})

defineEmits(['update:selectedTool'])
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

.panel-head {
  padding: 20px 20px 14px;
  border-bottom: 1px solid var(--border-subtle);
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.panel-subtitle {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.tool-tabs {
  display: flex;
  gap: 8px;
  overflow: auto;
  padding: 14px 16px 0;
}

.tool-tab {
  min-height: 34px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: var(--surface-muted);
  color: var(--text-secondary);
  padding: 0 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.16s ease;
}

.tool-tab.active {
  background: #111111;
  color: #ffffff;
  border-color: #111111;
}

.tool-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
}

.tool-card {
  padding: 16px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.72);
}

.tool-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.tool-query {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-all;
}

.tool-pre {
  margin-top: 12px;
  padding: 16px;
  border-radius: var(--radius-lg);
  background: rgba(17, 17, 17, 0.05);
  overflow: auto;
  white-space: pre-wrap;
  font-family: var(--ui-font-mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-primary);
}

.tool-search-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.tool-search-item {
  padding: 14px;
  border-radius: var(--radius-lg);
  background: rgba(17, 17, 17, 0.04);
}

.tool-search-item h4 {
  font-size: 13px;
  color: var(--text-primary);
}

.tool-search-item p,
.tool-search-item a {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
}

.tool-search-item a {
  color: var(--accent-ink);
  word-break: break-all;
}

.panel-empty {
  padding: 56px 18px;
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
