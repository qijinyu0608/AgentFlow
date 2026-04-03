<template>
  <section class="panel-shell">
    <div class="panel-head">
      <div>
        <div class="panel-title">协作调度</div>
        <div class="panel-subtitle">按团队、工具和 skill 粒度控制本次任务的运行策略。</div>
      </div>
    </div>

    <div class="dispatch-scroll">
      <article class="dispatch-card">
        <div class="dispatch-card-title">智能体团队</div>
        <label class="dispatch-field">
          <span>当前团队</span>
          <select :value="selectedTeam" @change="$emit('update:selectedTeam', $event.target.value)">
            <option v-for="team in availableTeams" :key="team.id" :value="team.id">{{ team.name }}</option>
          </select>
        </label>
      </article>

      <article class="dispatch-card">
        <div class="dispatch-card-head">
          <div class="dispatch-card-title">工具策略</div>
          <div class="dispatch-card-controls">
            <button
              type="button"
              class="dispatch-collapse-btn"
              :aria-expanded="isToolsSectionExpanded"
              :aria-label="isToolsSectionExpanded ? '收起工具策略' : '展开工具策略'"
              @click="isToolsSectionExpanded = !isToolsSectionExpanded"
            >
              <svg class="dispatch-collapse-icon" :class="{ expanded: isToolsSectionExpanded }" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
            <label class="dispatch-toggle">
              <input
                type="checkbox"
                :checked="useRuntimeToolsOverride"
                @change="$emit('update:useRuntimeToolsOverride', $event.target.checked)"
              />
              <span>覆盖默认工具</span>
            </label>
          </div>
        </div>

        <template v-if="isToolsSectionExpanded">
          <div v-if="selectedTeamAgents.length === 0" class="dispatch-empty">当前团队未配置智能体。</div>
          <div v-else-if="availableRuntimeTools.length === 0" class="dispatch-empty">暂无可用工具。</div>
          <div v-else class="dispatch-groups">
            <div v-for="agentName in selectedTeamAgents" :key="`dispatch-tools-${agentName}`" class="dispatch-group">
              <div class="dispatch-group-top">
                <div class="dispatch-group-name">{{ agentName }}</div>
                <div class="dispatch-group-default">默认：{{ formatCapabilityList(getAgentDefaultTools(agentName)) }}</div>
              </div>

              <div class="dispatch-chip-list">
                <label
                  v-for="tool in availableRuntimeTools"
                  :key="`tool-${agentName}-${tool.name}`"
                  class="dispatch-chip"
                  :class="{ active: isToolSelectedForAgent(agentName, tool.name), locked: !useRuntimeToolsOverride }"
                >
                  <input
                    type="checkbox"
                    :checked="isToolSelectedForAgent(agentName, tool.name)"
                    :disabled="!useRuntimeToolsOverride"
                    @change="toggleAgentRuntimeTool(agentName, tool.name, $event.target.checked)"
                  />
                  <span>{{ tool.name }}</span>
                </label>
              </div>

              <div v-if="useRuntimeToolsOverride" class="dispatch-summary">
                本次启用：{{ formatCapabilityList(getAgentSelectedTools(agentName)) }}
              </div>
            </div>
          </div>

          <div v-if="useRuntimeToolsOverride" class="dispatch-preset-wrap">
            <div class="dispatch-preset-head">
              <div>
                <div class="dispatch-card-title">策略预设</div>
                <div class="dispatch-card-hint">先套用预设，再逐项微调。</div>
              </div>
              <button type="button" class="dispatch-link-btn" @click="resetRuntimeToolConfigsToBase">恢复默认</button>
            </div>

            <div class="dispatch-preset-list">
              <button
                v-for="preset in runtimeToolPresets"
                :key="preset.key"
                type="button"
                class="dispatch-preset-btn"
                :class="{ active: runtimeToolPreset === preset.key }"
                @click="applyRuntimeToolPreset(preset.key)"
              >
                <strong>{{ preset.label }}</strong>
                <span>{{ preset.description }}</span>
              </button>
            </div>
          </div>

          <div v-if="useRuntimeToolsOverride && configurableSelectedRuntimeTools.length" class="dispatch-config-grid">
            <div
              v-for="toolName in configurableSelectedRuntimeTools"
              :key="`tool-config-${toolName}`"
              class="dispatch-config-card"
            >
              <div class="dispatch-config-title">{{ toolName }}</div>
              <div class="dispatch-config-desc">{{ getRuntimeToolMeta(toolName)?.description || '运行时配置' }}</div>

              <div class="dispatch-config-fields">
                <div v-for="field in runtimeToolFieldDefs[toolName]" :key="`${toolName}-${field.key}`" class="dispatch-config-field">
                  <label>
                    <span>{{ field.label }}</span>
                    <input
                      v-if="field.type === 'boolean'"
                      type="checkbox"
                      :checked="Boolean(getRuntimeToolConfigValue(toolName, field.key, false))"
                      @change="updateRuntimeToolConfigValue(toolName, field.key, $event.target.checked)"
                    />
                  </label>
                  <input
                    v-if="field.type === 'text'"
                    class="dispatch-config-input"
                    :value="getRuntimeToolConfigValue(toolName, field.key, '')"
                    :placeholder="field.placeholder"
                    @input="updateRuntimeToolConfigValue(toolName, field.key, $event.target.value)"
                  />
                  <input
                    v-else-if="field.type === 'number'"
                    class="dispatch-config-input"
                    type="number"
                    :min="field.min"
                    :max="field.max"
                    :step="field.step || 1"
                    :value="getRuntimeToolConfigValue(toolName, field.key, '')"
                    :placeholder="field.placeholder"
                    @input="updateRuntimeToolConfigValue(toolName, field.key, $event.target.value)"
                  />
                  <div class="dispatch-config-help">{{ field.help }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </article>

      <article class="dispatch-card">
        <div class="dispatch-card-head">
          <div class="dispatch-card-title">Skill调度</div>
          <div class="dispatch-card-controls">
            <button
              type="button"
              class="dispatch-collapse-btn"
              :aria-expanded="isSkillsSectionExpanded"
              :aria-label="isSkillsSectionExpanded ? '收起Skill调度' : '展开Skill调度'"
              @click="isSkillsSectionExpanded = !isSkillsSectionExpanded"
            >
              <svg class="dispatch-collapse-icon" :class="{ expanded: isSkillsSectionExpanded }" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
            <label class="dispatch-toggle">
              <input
                type="checkbox"
                :checked="useRuntimeSkillsOverride"
                @change="$emit('update:useRuntimeSkillsOverride', $event.target.checked)"
              />
              <span>覆盖默认 skill</span>
            </label>
          </div>
        </div>

        <template v-if="isSkillsSectionExpanded">
          <div v-if="selectedTeamAgentProfiles.length === 0" class="dispatch-empty">当前团队未配置智能体。</div>
          <div v-else-if="availableSkills.length === 0" class="dispatch-empty">暂无可用 skill。</div>
          <div v-else class="dispatch-groups">
            <div v-for="agent in selectedTeamAgentProfiles" :key="`dispatch-skills-${agent.name}`" class="dispatch-group">
              <div class="dispatch-group-top">
                <div class="dispatch-group-name">{{ agent.name }}</div>
                <div class="dispatch-group-default">默认：{{ formatCapabilityList(agent.skills) }}</div>
              </div>

              <div class="dispatch-chip-list">
                <label
                  v-for="skill in availableSkills"
                  :key="`skill-${agent.name}-${skill.name}`"
                  class="dispatch-chip"
                  :class="{ active: isRuntimeSkillSelectedForAgent(agent.name, skill.name), locked: !useRuntimeSkillsOverride }"
                >
                  <input
                    type="checkbox"
                    :checked="isRuntimeSkillSelectedForAgent(agent.name, skill.name)"
                    :disabled="!useRuntimeSkillsOverride"
                    @change="toggleAgentRuntimeSkill(agent.name, skill.name, $event.target.checked)"
                  />
                  <span>{{ skill.name }}</span>
                </label>
              </div>

              <div v-if="useRuntimeSkillsOverride" class="dispatch-summary">
                本次启用：{{ formatCapabilityList(getAgentSelectedSkills(agent.name)) }}
              </div>
            </div>
          </div>
        </template>
      </article>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

const isToolsSectionExpanded = ref(true)
const isSkillsSectionExpanded = ref(true)

defineProps({
  selectedTeam: { type: String, default: '' },
  availableTeams: { type: Array, default: () => [] },
  selectedTeamAgents: { type: Array, default: () => [] },
  selectedTeamAgentProfiles: { type: Array, default: () => [] },
  availableRuntimeTools: { type: Array, default: () => [] },
  availableSkills: { type: Array, default: () => [] },
  useRuntimeToolsOverride: { type: Boolean, default: false },
  useRuntimeSkillsOverride: { type: Boolean, default: false },
  configurableSelectedRuntimeTools: { type: Array, default: () => [] },
  runtimeToolPresets: { type: Array, default: () => [] },
  runtimeToolPreset: { type: String, default: 'balanced' },
  runtimeToolFieldDefs: { type: Object, default: () => ({}) },
  formatCapabilityList: { type: Function, required: true },
  getAgentDefaultTools: { type: Function, required: true },
  getAgentSelectedTools: { type: Function, required: true },
  isToolSelectedForAgent: { type: Function, required: true },
  toggleAgentRuntimeTool: { type: Function, required: true },
  applyRuntimeToolPreset: { type: Function, required: true },
  resetRuntimeToolConfigsToBase: { type: Function, required: true },
  getRuntimeToolMeta: { type: Function, required: true },
  getRuntimeToolConfigValue: { type: Function, required: true },
  updateRuntimeToolConfigValue: { type: Function, required: true },
  isRuntimeSkillSelectedForAgent: { type: Function, required: true },
  getAgentSelectedSkills: { type: Function, required: true },
  toggleAgentRuntimeSkill: { type: Function, required: true },
})

defineEmits([
  'update:selectedTeam',
  'update:useRuntimeToolsOverride',
  'update:useRuntimeSkillsOverride',
])
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

.dispatch-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dispatch-card {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  padding: 16px;
  background: rgba(255, 255, 255, 0.72);
}

.dispatch-card-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.dispatch-card-hint,
.dispatch-group-default,
.dispatch-summary,
.dispatch-empty,
.dispatch-config-help,
.dispatch-config-desc {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.dispatch-card-head,
.dispatch-preset-head,
.dispatch-group-top,
.dispatch-field label,
.dispatch-config-field label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dispatch-card-controls {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.dispatch-collapse-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: #ffffff;
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, transform 0.16s ease;
}

.dispatch-collapse-btn:hover {
  background: rgba(17, 17, 17, 0.04);
  color: var(--text-primary);
  transform: translateY(-1px);
}

.dispatch-collapse-icon {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
  transform: rotate(0deg);
  transition: transform 0.18s ease;
}

.dispatch-collapse-icon.expanded {
  transform: rotate(180deg);
}

.dispatch-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.dispatch-field span {
  color: var(--text-muted);
  font-size: 12px;
}

.dispatch-field select,
.dispatch-config-input {
  width: 100%;
  min-height: 38px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: #ffffff;
  color: var(--text-primary);
  font: inherit;
  padding: 0 12px;
}

.dispatch-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  cursor: pointer;
  background: var(--surface-muted);
  color: var(--text-secondary);
  font-size: 12px;
}

.dispatch-toggle input {
  margin: 0;
  accent-color: #111111;
}

.dispatch-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.dispatch-group {
  padding: 14px;
  border-radius: var(--radius-lg);
  background: rgba(17, 17, 17, 0.03);
}

.dispatch-group-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.dispatch-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.dispatch-chip {
  min-height: 34px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  background: #ffffff;
  color: var(--text-secondary);
  cursor: pointer;
}

.dispatch-chip.active {
  color: var(--text-primary);
  border-color: rgba(17, 17, 17, 0.14);
  background: rgba(17, 17, 17, 0.06);
}

.dispatch-chip.locked {
  opacity: 0.72;
}

.dispatch-chip input {
  margin: 0;
  accent-color: #111111;
}

.dispatch-preset-wrap,
.dispatch-config-grid {
  margin-top: 14px;
}

.dispatch-preset-list,
.dispatch-config-grid {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}

.dispatch-preset-btn,
.dispatch-link-btn {
  border: 1px solid var(--border-subtle);
  background: #ffffff;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
}

.dispatch-preset-btn {
  text-align: left;
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dispatch-preset-btn.active {
  background: rgba(17, 17, 17, 0.06);
  color: var(--text-primary);
}

.dispatch-link-btn {
  min-height: 32px;
  border-radius: var(--radius-md);
  padding: 0 12px;
}

.dispatch-config-card {
  padding: 14px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  background: #ffffff;
}

.dispatch-config-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.dispatch-config-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.dispatch-config-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dispatch-config-field label span {
  color: var(--text-secondary);
  font-size: 12px;
}

.dispatch-config-field input[type='checkbox'] {
  margin: 0;
  accent-color: #111111;
}
</style>
