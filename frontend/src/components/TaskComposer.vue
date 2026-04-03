<template>
  <div class="composer-shell" :class="{ elevated, compact }">
    <div class="composer-row">
      <div class="composer-input-wrap">
        <textarea
          ref="textareaRef"
          class="composer-input"
          :value="modelValue"
          :placeholder="placeholder"
          :disabled="disabled || loading"
          rows="1"
          @input="handleInput"
          @keydown="$emit('keydown', $event)"
        />
      </div>

      <button
        type="button"
        class="composer-send"
        :disabled="disabled || loading || !modelValue.trim()"
        @click="$emit('send')"
        aria-label="发送"
      >
        <svg v-if="!loading" width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 5L12 19M12 5L6.5 10.5M12 5L17.5 10.5"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span v-else class="composer-loader"></span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入你的任务需求' },
  selectedTeam: { type: String, default: '' },
  availableTeams: { type: Array, default: () => [] },
  useRuntimeToolsOverride: { type: Boolean, default: false },
  useRuntimeSkillsOverride: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  elevated: { type: Boolean, default: false },
  showOverrides: { type: Boolean, default: true },
  statusText: { type: String, default: '' },
})

const emit = defineEmits([
  'update:modelValue',
  'update:selectedTeam',
  'update:useRuntimeToolsOverride',
  'update:useRuntimeSkillsOverride',
  'keydown',
  'send',
])

const textareaRef = ref(null)

const resize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, props.compact ? 104 : 120)}px`
}

const handleInput = (event) => {
  emit('update:modelValue', event.target.value)
  nextTick(resize)
}

const focus = () => {
  textareaRef.value?.focus()
}

defineExpose({ focus })

watch(() => props.modelValue, () => nextTick(resize))

onMounted(() => {
  resize()
})
</script>

<style scoped>
.composer-shell {
  position: relative;
  border: 1px solid var(--border-subtle);
  background: var(--surface-elevated);
  box-shadow: var(--shadow-soft);
  border-radius: var(--radius-3xl);
  padding: 10px 12px;
  backdrop-filter: blur(18px);
}

.composer-shell.elevated {
  box-shadow: var(--shadow-large);
}

.composer-shell.compact {
  border-radius: var(--radius-xl);
  padding: 8px 10px;
}

.composer-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.composer-input-wrap {
  min-height: 56px;
  flex: 1;
}

.composer-shell.compact .composer-input-wrap {
  min-height: 52px;
}

.composer-input {
  width: 100%;
  min-height: 40px;
  max-height: 120px;
  border: 0;
  resize: none;
  background: transparent;
  color: var(--text-primary);
  font: inherit;
  font-size: 16px;
  line-height: 1.6;
  outline: none;
}

.composer-input::placeholder {
  color: var(--text-muted);
}

.composer-send {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border: 0;
  border-radius: var(--radius-pill);
  background: #111111;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.16s ease, opacity 0.16s ease, box-shadow 0.16s ease;
  box-shadow: 0 8px 20px rgba(17, 17, 17, 0.18);
}

.composer-send:hover:not(:disabled) {
  transform: translateY(-1px);
}

.composer-send:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  box-shadow: none;
}

.composer-loader {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-pill);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  animation: composer-spin 0.7s linear infinite;
}

@keyframes composer-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .composer-shell {
    border-radius: var(--radius-lg);
    padding: 8px 10px;
  }

  .composer-send {
    width: 36px;
    height: 36px;
  }
}
</style>
