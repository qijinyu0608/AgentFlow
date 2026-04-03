<template>
  <aside class="sidebar-shell" :class="{ collapsed }">
    <div class="sidebar-top">
      <div class="sidebar-brand" :class="{ collapsed }">
        <div class="sidebar-brand-mark">A</div>
        <div v-if="!collapsed" class="sidebar-brand-copy">
          <div class="sidebar-brand-title">AgentMesh</div>
          <div class="sidebar-brand-subtitle">桌面工作台</div>
        </div>
      </div>

    </div>

    <nav class="sidebar-nav">
      <button type="button" class="nav-item nav-item--primary" :class="{ active: currentView === 'welcome' || currentView === 'chat' }" @click="$emit('new-session')">
        <span class="nav-item-icon">+</span>
        <span v-if="!collapsed">新线程</span>
      </button>
      <button type="button" class="nav-item" :class="{ active: currentView === 'memory' }" @click="$emit('open-view', 'memory')">
        <span class="nav-item-icon">M</span>
        <span v-if="!collapsed">长期记忆</span>
      </button>
      <button type="button" class="nav-item" :class="{ active: currentView === 'config' }" @click="$emit('open-view', 'config')">
        <span class="nav-item-icon">T</span>
        <span v-if="!collapsed">团队配置</span>
      </button>
      <button type="button" class="nav-item" :class="{ active: currentView === 'rag' }" @click="$emit('open-view', 'rag')">
        <span class="nav-item-icon">K</span>
        <span v-if="!collapsed">知识库</span>
      </button>
      <button
        v-if="canOpenDetail"
        type="button"
        class="nav-item"
        :class="{ active: currentView === 'detail' }"
        @click="$emit('open-view', 'detail')"
      >
        <span class="nav-item-icon">D</span>
        <span v-if="!collapsed">协作详情</span>
      </button>
    </nav>

    <div v-if="!collapsed" class="sidebar-thread-head">
      <div>
        <div class="sidebar-section-title">线程</div>
        <div class="sidebar-section-subtitle">{{ sessionsCount }} 条历史</div>
      </div>
      <button type="button" class="sidebar-new-btn" @click="$emit('new-session')">新建</button>
    </div>

    <div v-if="!collapsed" class="sidebar-threads">
      <div v-if="groupedSessions.length === 0" class="sidebar-empty">
        <div>暂无历史记录</div>
        <p>开始一次对话后会自动保存在这里。</p>
      </div>

      <section v-for="group in groupedSessions" :key="group.key" class="thread-group">
        <div class="thread-group-label">{{ group.label }}</div>

        <div
          v-for="session in group.items"
          :key="session.id"
          class="thread-item"
          :class="{ active: session.id === activeSessionId }"
          @click="$emit('select-session', session.id)"
        >
          <div class="thread-item-main">
            <span class="thread-indicator" :class="session.status"></span>
            <div class="thread-copy">
              <h4 class="thread-title">
                <template v-if="renamingSessionId === session.id">
                  <input
                    class="thread-rename-input"
                    :value="renameDraft"
                    @click.stop
                    @input="$emit('update:renameDraft', $event.target.value)"
                    @keydown.enter.prevent="$emit('confirm-rename', session.id)"
                    @keydown.esc.prevent="$emit('cancel-rename')"
                    @blur="$emit('confirm-rename', session.id)"
                  />
                </template>
                <template v-else>
                  {{ session.title }}
                </template>
              </h4>
              <p v-if="getSessionSubtitle(session)" class="thread-subtitle">{{ getSessionSubtitle(session) }}</p>
            </div>
          </div>

          <div class="thread-meta">
            <span class="thread-time">{{ formatSidebarTime(session.updatedAt) }}</span>
            <div class="thread-actions" @click.stop>
              <button type="button" class="thread-icon-btn" title="改名" aria-label="改名" @click.stop="$emit('start-rename', session)">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M4 20H8L18.2 9.8a1.7 1.7 0 0 0 0-2.4l-1.6-1.6a1.7 1.7 0 0 0-2.4 0L4 16v4Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </button>
              <button type="button" class="thread-icon-btn thread-icon-btn--danger" title="删除" aria-label="删除" @click.stop="$emit('delete-session', session.id)">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M4 7H20M9 7V5h6v2m-7 0 1 12h6l1-12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  collapsed: { type: Boolean, default: false },
  currentView: { type: String, default: 'welcome' },
  canOpenDetail: { type: Boolean, default: false },
  sessionsCount: { type: Number, default: 0 },
  groupedSessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: null },
  renamingSessionId: { type: String, default: null },
  renameDraft: { type: String, default: '' },
  getSessionSubtitle: { type: Function, required: true },
  formatSidebarTime: { type: Function, required: true },
})

defineEmits([
  'new-session',
  'open-view',
  'select-session',
  'update:renameDraft',
  'start-rename',
  'confirm-rename',
  'cancel-rename',
  'delete-session',
])
</script>

<style scoped>
.sidebar-shell {
  display: flex;
  flex-direction: column;
  width: 318px;
  min-width: 318px;
  height: 100%;
  padding: 16px 14px 16px 16px;
  border-right: 1px solid var(--border-subtle);
  background: #ffffff;
  transition: width 0.25s ease, min-width 0.25s ease, padding 0.25s ease;
}

.sidebar-shell.collapsed {
  width: 84px;
  min-width: 84px;
  padding-inline: 12px;
}

.sidebar-top,
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sidebar-top {
  margin-bottom: 20px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 44px;
}

.sidebar-brand.collapsed {
  justify-content: center;
}

.sidebar-brand-mark {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: #111111;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
}

.sidebar-brand-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-brand-subtitle {
  font-size: 11px;
  color: var(--text-muted);
}

.sidebar-new-btn,
.nav-item,
.thread-icon-btn {
  border: 1px solid var(--border-subtle);
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
}

.nav-item {
  min-height: 42px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  cursor: pointer;
  transition: all 0.16s ease;
}

.nav-item:hover,
.thread-icon-btn:hover,
.sidebar-new-btn:hover {
  background: rgba(0, 0, 0, 0.03);
}

.nav-item.active {
  background: rgba(17, 17, 17, 0.06);
  color: var(--text-primary);
  border-color: rgba(17, 17, 17, 0.1);
}

.nav-item--primary {
  background: #111111;
  color: #ffffff;
  border-color: #111111;
}

.nav-item--primary.active {
  background: #111111;
  color: #ffffff;
}

.nav-item-icon {
  width: 20px;
  text-align: center;
  font-size: 13px;
  font-weight: 700;
}

.sidebar-shell.collapsed .nav-item {
  justify-content: center;
  padding-inline: 0;
}

.sidebar-thread-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 20px 0 14px;
  padding: 0 4px;
}

.sidebar-section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}

.sidebar-section-subtitle {
  font-size: 11px;
  color: var(--text-muted);
}

.sidebar-new-btn {
  min-height: 34px;
  border-radius: var(--radius-md);
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.sidebar-threads {
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}

.sidebar-empty {
  padding: 24px 10px;
  color: var(--text-muted);
  font-size: 12px;
}

.sidebar-empty p {
  margin-top: 6px;
}

.thread-group + .thread-group {
  margin-top: 14px;
}

.thread-group-label {
  padding: 0 8px 8px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.thread-item {
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  margin: 0 8px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.16s ease;
}

.thread-item:hover {
  background: rgba(0, 0, 0, 0.03);
  border-color: var(--border-subtle);
}

.thread-item.active {
  background: #ffffff;
  border-color: rgba(17, 17, 17, 0.1);
  box-shadow: inset 0 0 0 1px rgba(17, 17, 17, 0.04);
}

.thread-item-main,
.thread-meta,
.thread-actions {
  display: flex;
}

.thread-item-main {
  gap: 10px;
  min-width: 0;
}

.thread-copy {
  min-width: 0;
  flex: 1;
}

.thread-indicator {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: var(--radius-pill);
  background: rgba(17, 17, 17, 0.18);
}

.thread-indicator.running {
  background: #1f5d42;
}

.thread-indicator.failed {
  background: #b16e6e;
}

.thread-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.35;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.thread-subtitle {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.35;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.thread-meta {
  margin-top: 8px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.thread-time {
  font-size: 11px;
  color: var(--text-muted);
}

.thread-actions {
  gap: 6px;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.thread-item:hover .thread-actions,
.thread-item.active .thread-actions {
  opacity: 1;
}

.thread-icon-btn {
  width: 28px;
  min-width: 28px;
  min-height: 28px;
  border-radius: var(--radius-sm);
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.thread-icon-btn svg {
  width: 13px;
  height: 13px;
}

.thread-icon-btn--danger:hover {
  background: rgba(177, 110, 110, 0.12);
  color: #8b4848;
}

.thread-rename-input {
  width: 100%;
  min-height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  background: #ffffff;
  padding: 0 10px;
  font: inherit;
  color: var(--text-primary);
  outline: none;
}
</style>
