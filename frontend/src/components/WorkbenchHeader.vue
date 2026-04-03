<template>
  <header class="header-shell">
    <div class="header-main">
      <button type="button" class="header-icon-btn" @click="$emit('toggle-sidebar')" aria-label="切换侧栏">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <path d="M4 6H20M4 12H14M4 18H20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
        </svg>
      </button>

      <button v-if="showBack" type="button" class="header-back-btn" @click="$emit('back')">
        {{ backLabel }}
      </button>

      <div class="header-copy">
        <div class="header-title">{{ title }}</div>
        <div v-if="subtitle" class="header-subtitle">{{ subtitle }}</div>
      </div>
    </div>

    <div class="header-actions">
      <div class="header-status">
        <span class="status-pill" :class="`status-pill--${wsStatus}`">{{ wsLabel }}</span>
        <span v-if="isAgentRunning" class="status-pill status-pill--live">运行中</span>
        <span v-if="currentTaskId" class="status-pill">任务 {{ currentTaskId }}</span>
      </div>

      <button type="button" class="header-action-btn" @click="$emit('create-session')">新线程</button>
      <button v-if="showExport" type="button" class="header-action-btn header-action-btn--strong" @click="$emit('export-markdown')">
        导出 Markdown
      </button>
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  wsStatus: { type: String, default: 'disconnected' },
  wsLabel: { type: String, default: '' },
  isAgentRunning: { type: Boolean, default: false },
  currentTaskId: { type: String, default: null },
  showBack: { type: Boolean, default: false },
  backLabel: { type: String, default: '返回会话' },
  showExport: { type: Boolean, default: false },
})

defineEmits([
  'toggle-sidebar',
  'back',
  'create-session',
  'export-markdown',
])
</script>

<style scoped>
.header-shell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 72px;
  padding: 12px 20px 18px;
  border-bottom: 1px solid var(--border-subtle);
}

.header-main,
.header-actions,
.header-status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-main {
  min-width: 0;
  flex: 1;
}

.header-copy {
  min-width: 0;
}

.header-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.header-icon-btn,
.header-back-btn,
.header-action-btn {
  min-height: 38px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: var(--surface-elevated);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.16s ease, transform 0.16s ease, border-color 0.16s ease;
}

.header-icon-btn {
  width: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.header-back-btn,
.header-action-btn {
  padding: 0 14px;
  font: inherit;
  font-size: 12px;
}

.header-icon-btn:hover,
.header-back-btn:hover,
.header-action-btn:hover:not(.header-action-btn--strong) {
  background: #ffffff;
  transform: translateY(-1px);
}

.header-action-btn--strong {
  background: #111111;
  color: #ffffff;
  border-color: #111111;
}

.header-action-btn--strong:hover {
  background: #1f1f1f;
  color: #ffffff;
  border-color: #1f1f1f;
  transform: translateY(-1px);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: var(--surface-muted);
  color: var(--text-secondary);
  font-size: 12px;
}

.status-pill--connected {
  color: #295f45;
  background: rgba(115, 160, 129, 0.12);
}

.status-pill--connecting {
  color: #7b5a1b;
  background: rgba(184, 147, 72, 0.12);
}

.status-pill--disconnected {
  color: #7f4a4a;
  background: rgba(177, 110, 110, 0.12);
}

.status-pill--live {
  background: rgba(17, 17, 17, 0.08);
  color: var(--text-primary);
}

@media (max-width: 1100px) {
  .header-shell {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
