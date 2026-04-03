<template>
  <section class="welcome-shell">
    <div class="welcome-center">
      <div class="welcome-mark">
        <span></span>
      </div>
      <h1 class="welcome-title">{{ title }}</h1>
      <p class="welcome-subtitle">{{ subtitle }}</p>
      <div class="welcome-workspace">{{ workspaceLabel }}</div>

      <div class="welcome-actions">
        <button type="button" class="welcome-action" @click="$emit('open-memory')">长期记忆</button>
        <button type="button" class="welcome-action" @click="$emit('open-config')">团队配置</button>
        <button type="button" class="welcome-action" @click="$emit('open-rag')">知识库上传</button>
      </div>
    </div>

    <div class="welcome-composer">
      <TaskComposer
        ref="composerRef"
        :model-value="modelValue"
        :placeholder="placeholder"
        :selected-team="selectedTeam"
        :available-teams="availableTeams"
        :use-runtime-tools-override="useRuntimeToolsOverride"
        :use-runtime-skills-override="useRuntimeSkillsOverride"
        :loading="loading"
        :elevated="true"
        status-text="在这里发起一个复杂任务"
        @update:model-value="$emit('update:modelValue', $event)"
        @update:selected-team="$emit('update:selectedTeam', $event)"
        @update:use-runtime-tools-override="$emit('update:useRuntimeToolsOverride', $event)"
        @update:use-runtime-skills-override="$emit('update:useRuntimeSkillsOverride', $event)"
        @keydown="$emit('keydown', $event)"
        @send="$emit('send')"
      />
    </div>

    <div class="welcome-prompt-grid">
      <button
        v-for="example in examplePrompts"
        :key="example"
        type="button"
        class="welcome-prompt"
        @click="$emit('set-example', example)"
      >
        {{ example }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import TaskComposer from './TaskComposer.vue'

defineProps({
  title: { type: String, default: '开始构建' },
  subtitle: { type: String, default: '' },
  workspaceLabel: { type: String, default: '' },
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入你的任务需求' },
  selectedTeam: { type: String, default: '' },
  availableTeams: { type: Array, default: () => [] },
  useRuntimeToolsOverride: { type: Boolean, default: false },
  useRuntimeSkillsOverride: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  examplePrompts: { type: Array, default: () => [] },
})

defineEmits([
  'update:modelValue',
  'update:selectedTeam',
  'update:useRuntimeToolsOverride',
  'update:useRuntimeSkillsOverride',
  'keydown',
  'send',
  'set-example',
  'open-memory',
  'open-config',
  'open-rag',
])

const composerRef = ref(null)

defineExpose({
  focus: () => composerRef.value?.focus?.(),
})
</script>

<style scoped>
.welcome-shell {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px 26px;
}

.welcome-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.welcome-mark {
  width: 58px;
  height: 58px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--shadow-soft);
}

.welcome-mark span {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-pill);
  border: 2px solid #111111;
  position: relative;
}

.welcome-mark span::before,
.welcome-mark span::after {
  content: '';
  position: absolute;
  border-radius: var(--radius-pill);
  border: 2px solid #111111;
}

.welcome-mark span::before {
  inset: -8px 3px 3px -8px;
}

.welcome-mark span::after {
  inset: 3px -8px -8px 3px;
}

.welcome-title {
  margin-top: 28px;
  font-size: clamp(42px, 5vw, 56px);
  line-height: 1.04;
  letter-spacing: -0.05em;
  color: var(--text-primary);
}

.welcome-subtitle {
  margin-top: 14px;
  font-size: 17px;
  color: var(--text-secondary);
}

.welcome-workspace {
  margin-top: 10px;
  font-size: clamp(24px, 3vw, 36px);
  color: rgba(17, 17, 17, 0.48);
  line-height: 1.1;
}

.welcome-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 30px;
}

.welcome-action {
  min-height: 40px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.68);
  color: var(--text-secondary);
  padding: 0 14px;
  font: inherit;
  cursor: pointer;
}

.welcome-composer {
  width: min(980px, 100%);
  margin-top: 48px;
}

.welcome-prompt-grid {
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.welcome-prompt {
  min-height: 64px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.64);
  color: var(--text-secondary);
  padding: 14px 16px;
  text-align: left;
  font: inherit;
  line-height: 1.5;
  cursor: pointer;
  transition: background 0.16s ease, transform 0.16s ease;
}

.welcome-prompt:hover {
  background: rgba(255, 255, 255, 0.84);
  transform: translateY(-1px);
}

@media (max-width: 768px) {
  .welcome-prompt-grid {
    grid-template-columns: 1fr;
  }

  .welcome-shell {
    padding-inline: 10px;
  }
}
</style>
