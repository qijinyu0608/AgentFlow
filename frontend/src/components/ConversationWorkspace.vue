<template>
  <section class="workspace-shell">
    <div class="workspace-grid" :class="{ compact: isCompact }">
      <ProcessPanel
        class="workspace-process"
        :workflow-events="workflowEvents"
        :agent-messages="agentMessages"
        :selected-team="selectedTeam"
        :current-task-id="currentTaskId"
        :format-log-time="formatLogTime"
        :format-response="formatResponse"
        :workflow-handoff-payload="workflowHandoffPayload"
        :format-workflow-json="formatWorkflowJson"
        :set-container-ref="setMessagesContainer"
        @open-detail="$emit('open-detail')"
      />

      <template v-if="isCompact">
        <section class="workspace-secondary-shell">
          <div class="workspace-secondary-tabs">
            <button
              type="button"
              class="workspace-secondary-tab"
              :class="{ active: secondaryPanel === 'dispatch' }"
              @click="$emit('update:secondaryPanel', 'dispatch')"
            >
              协作调度
            </button>
            <button
              type="button"
              class="workspace-secondary-tab"
              :class="{ active: secondaryPanel === 'tools' }"
              @click="$emit('update:secondaryPanel', 'tools')"
            >
              工具结果
            </button>
          </div>

          <DispatchPanel
            v-if="secondaryPanel === 'dispatch'"
            class="workspace-secondary-panel"
            :selected-team="selectedTeam"
            :available-teams="availableTeams"
            :selected-team-agents="selectedTeamAgents"
            :selected-team-agent-profiles="selectedTeamAgentProfiles"
            :available-runtime-tools="availableRuntimeTools"
            :available-skills="availableSkills"
            :use-runtime-tools-override="useRuntimeToolsOverride"
            :use-runtime-skills-override="useRuntimeSkillsOverride"
            :configurable-selected-runtime-tools="configurableSelectedRuntimeTools"
            :runtime-tool-presets="runtimeToolPresets"
            :runtime-tool-preset="runtimeToolPreset"
            :runtime-tool-field-defs="runtimeToolFieldDefs"
            :format-capability-list="formatCapabilityList"
            :get-agent-default-tools="getAgentDefaultTools"
            :get-agent-selected-tools="getAgentSelectedTools"
            :is-tool-selected-for-agent="isToolSelectedForAgent"
            :toggle-agent-runtime-tool="toggleAgentRuntimeTool"
            :apply-runtime-tool-preset="applyRuntimeToolPreset"
            :reset-runtime-tool-configs-to-base="resetRuntimeToolConfigsToBase"
            :get-runtime-tool-meta="getRuntimeToolMeta"
            :get-runtime-tool-config-value="getRuntimeToolConfigValue"
            :update-runtime-tool-config-value="updateRuntimeToolConfigValue"
            :is-runtime-skill-selected-for-agent="isRuntimeSkillSelectedForAgent"
            :get-agent-selected-skills="getAgentSelectedSkills"
            :toggle-agent-runtime-skill="toggleAgentRuntimeSkill"
            @update:selected-team="$emit('update:selectedTeam', $event)"
            @update:use-runtime-tools-override="$emit('update:useRuntimeToolsOverride', $event)"
            @update:use-runtime-skills-override="$emit('update:useRuntimeSkillsOverride', $event)"
          />

          <ToolResultsPanel
            v-else
            class="workspace-secondary-panel"
            :active-tools="activeTools"
            :selected-tool="selectedTool"
            :selected-tool-data="selectedToolData"
            @update:selected-tool="$emit('update:selectedTool', $event)"
          />
        </section>
      </template>

      <template v-else>
        <DispatchPanel
          class="workspace-dispatch"
          :selected-team="selectedTeam"
          :available-teams="availableTeams"
          :selected-team-agents="selectedTeamAgents"
          :selected-team-agent-profiles="selectedTeamAgentProfiles"
          :available-runtime-tools="availableRuntimeTools"
          :available-skills="availableSkills"
          :use-runtime-tools-override="useRuntimeToolsOverride"
          :use-runtime-skills-override="useRuntimeSkillsOverride"
          :configurable-selected-runtime-tools="configurableSelectedRuntimeTools"
          :runtime-tool-presets="runtimeToolPresets"
          :runtime-tool-preset="runtimeToolPreset"
          :runtime-tool-field-defs="runtimeToolFieldDefs"
          :format-capability-list="formatCapabilityList"
          :get-agent-default-tools="getAgentDefaultTools"
          :get-agent-selected-tools="getAgentSelectedTools"
          :is-tool-selected-for-agent="isToolSelectedForAgent"
          :toggle-agent-runtime-tool="toggleAgentRuntimeTool"
          :apply-runtime-tool-preset="applyRuntimeToolPreset"
          :reset-runtime-tool-configs-to-base="resetRuntimeToolConfigsToBase"
          :get-runtime-tool-meta="getRuntimeToolMeta"
          :get-runtime-tool-config-value="getRuntimeToolConfigValue"
          :update-runtime-tool-config-value="updateRuntimeToolConfigValue"
          :is-runtime-skill-selected-for-agent="isRuntimeSkillSelectedForAgent"
          :get-agent-selected-skills="getAgentSelectedSkills"
          :toggle-agent-runtime-skill="toggleAgentRuntimeSkill"
          @update:selected-team="$emit('update:selectedTeam', $event)"
          @update:use-runtime-tools-override="$emit('update:useRuntimeToolsOverride', $event)"
          @update:use-runtime-skills-override="$emit('update:useRuntimeSkillsOverride', $event)"
        />

        <ToolResultsPanel
          class="workspace-tools"
          :active-tools="activeTools"
          :selected-tool="selectedTool"
          :selected-tool-data="selectedToolData"
          @update:selected-tool="$emit('update:selectedTool', $event)"
        />
      </template>
    </div>

    <div class="workspace-composer">
      <TaskComposer
        ref="composerRef"
        compact
        elevated
        :model-value="modelValue"
        :placeholder="placeholder"
        :selected-team="selectedTeam"
        :available-teams="availableTeams"
        :use-runtime-tools-override="useRuntimeToolsOverride"
        :use-runtime-skills-override="useRuntimeSkillsOverride"
        :loading="loading"
        status-text="底部统一输入器"
        @update:model-value="$emit('update:modelValue', $event)"
        @update:selected-team="$emit('update:selectedTeam', $event)"
        @update:use-runtime-tools-override="$emit('update:useRuntimeToolsOverride', $event)"
        @update:use-runtime-skills-override="$emit('update:useRuntimeSkillsOverride', $event)"
        @keydown="$emit('keydown', $event)"
        @send="$emit('send')"
      />
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import DispatchPanel from './DispatchPanel.vue'
import ProcessPanel from './ProcessPanel.vue'
import TaskComposer from './TaskComposer.vue'
import ToolResultsPanel from './ToolResultsPanel.vue'

defineProps({
  workflowEvents: { type: Array, default: () => [] },
  agentMessages: { type: Array, default: () => [] },
  activeTools: { type: Array, default: () => [] },
  selectedTool: { type: String, default: null },
  selectedToolData: { type: Object, default: null },
  selectedTeam: { type: String, default: '' },
  availableTeams: { type: Array, default: () => [] },
  availableRuntimeTools: { type: Array, default: () => [] },
  availableSkills: { type: Array, default: () => [] },
  selectedTeamAgents: { type: Array, default: () => [] },
  selectedTeamAgentProfiles: { type: Array, default: () => [] },
  useRuntimeToolsOverride: { type: Boolean, default: false },
  useRuntimeSkillsOverride: { type: Boolean, default: false },
  configurableSelectedRuntimeTools: { type: Array, default: () => [] },
  runtimeToolPresets: { type: Array, default: () => [] },
  runtimeToolPreset: { type: String, default: 'balanced' },
  runtimeToolFieldDefs: { type: Object, default: () => ({}) },
  currentTaskId: { type: String, default: null },
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入你的任务需求' },
  loading: { type: Boolean, default: false },
  isCompact: { type: Boolean, default: false },
  secondaryPanel: { type: String, default: 'dispatch' },
  setMessagesContainer: { type: Function, default: null },
  formatLogTime: { type: Function, required: true },
  formatResponse: { type: Function, required: true },
  workflowHandoffPayload: { type: Function, required: true },
  formatWorkflowJson: { type: Function, required: true },
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
  'open-detail',
  'update:selectedTool',
  'update:selectedTeam',
  'update:useRuntimeToolsOverride',
  'update:useRuntimeSkillsOverride',
  'update:modelValue',
  'update:secondaryPanel',
  'keydown',
  'send',
])

const composerRef = ref(null)

defineExpose({
  focus: () => composerRef.value?.focus?.(),
})
</script>

<style scoped>
.workspace-shell {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow: hidden;
}

.workspace-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.92fr) minmax(320px, 0.92fr);
  gap: 16px;
  overflow: hidden;
}

.workspace-grid.compact {
  grid-template-columns: minmax(0, 1fr);
}

.workspace-process,
.workspace-dispatch,
.workspace-tools,
.workspace-secondary-shell {
  min-height: 0;
}

.workspace-secondary-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.workspace-secondary-tabs {
  display: flex;
  gap: 8px;
}

.workspace-secondary-tab {
  min-height: 38px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-secondary);
  padding: 0 14px;
  font: inherit;
  cursor: pointer;
}

.workspace-secondary-tab.active {
  background: #111111;
  color: #ffffff;
  border-color: #111111;
}

.workspace-secondary-panel {
  flex: 1;
}

.workspace-composer {
  flex-shrink: 0;
  padding-bottom: 4px;
}

@media (max-width: 1380px) {
  .workspace-grid {
    grid-template-columns: minmax(0, 1.32fr) minmax(300px, 0.9fr) minmax(300px, 0.9fr);
  }
}

</style>
