<template>
  <div class="cfg" :class="{ embedded: props.embedded }">
    <div class="top">
      <div class="left">
        <div class="title">智能体团队 / 模型配置</div>
        <div class="sub">先验证结构、连通性和团队预览，再决定是否写入 `config.yaml`。</div>
      </div>
      <div class="right">
        <button class="btn" :disabled="saving || validating" type="button" @click="validateConfig">
          {{ validating ? '验证中…' : '验证配置' }}
        </button>
        <button class="btn" :disabled="saving" type="button" @click="save">
          {{ saving ? '保存中…' : '保存到 config.yaml' }}
        </button>
      </div>
    </div>

    <div v-if="notice" class="notice" :class="notice.type">
      {{ notice.text }}
    </div>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else class="content">
      <div class="workspaceStats">
        <div class="workspaceStat">
          <div class="workspaceStatLabel">团队</div>
          <div class="workspaceStatValue">{{ teams.length }}</div>
        </div>
        <div class="workspaceStat">
          <div class="workspaceStatLabel">Agent</div>
          <div class="workspaceStatValue">{{ totalAgentCount }}</div>
        </div>
        <div class="workspaceStat">
          <div class="workspaceStatLabel">Provider</div>
          <div class="workspaceStatValue">{{ providers.length }}</div>
        </div>
        <div class="workspaceStat">
          <div class="workspaceStatLabel">已发现 Skill</div>
          <div class="workspaceStatValue">{{ availableSkills.length }}</div>
        </div>
      </div>

      <div class="workspaceGuide">
        <div class="guideCard">
          <div class="guideLabel">团队编排</div>
          <div class="guideValue">{{ currentTeam?.key || teams[0]?.key || '未选择 team' }}</div>
          <div class="guideText">
            {{ currentTeam ? `当前团队包含 ${currentTeam.agents.length} 个 Agent，可直接在下方集中编辑成员与规则。`
              : '先选择一个 team，再集中编辑团队模型、规则和 agents。' }}
          </div>
        </div>

        <div class="guideCard">
          <div class="guideLabel">模型连接</div>
          <div class="guideValue">{{ providers.length }} / {{ allModelNames.length }}</div>
          <div class="guideText">左值是 Provider 数量，右值是当前已配置的模型总数，便于先确认运行入口是否完整。</div>
        </div>

        <div class="guideCard">
          <div class="guideLabel">Skill 接入</div>
          <div class="guideValue">{{ skillPathCount }} 条路径</div>
          <div class="guideText">已发现 {{ availableSkills.length }} 个 skill；推荐先补路径，再做验证，这样结果会更完整。</div>
        </div>
      </div>

      <div v-if="validationResult" class="validationCard">
        <div class="validationHeader">
          <div>
            <div class="validationTitle">验证结果</div>
            <div class="validationSub">
              结构校验、Provider 连通性和团队预览都会显示在这里。
            </div>
          </div>
          <span class="validationBadge" :class="validationResult.ok ? 'ok' : 'error'">
            {{ validationResult.ok ? '可保存' : '需处理' }}
          </span>
        </div>

        <div class="validationSummary">
          <div class="summaryItem">
            <div class="summaryLabel">错误</div>
            <div class="summaryValue">{{ validationResult.errors?.length || 0 }}</div>
          </div>
          <div class="summaryItem">
            <div class="summaryLabel">警告</div>
            <div class="summaryValue">{{ validationResult.warnings?.length || 0 }}</div>
          </div>
          <div class="summaryItem">
            <div class="summaryLabel">Provider 检查</div>
            <div class="summaryValue">{{ validationResult.provider_checks?.length || 0 }}</div>
          </div>
        </div>

        <div v-if="validationResult.errors?.length" class="validationList">
          <div class="validationListTitle bad">错误</div>
          <div v-for="item in validationResult.errors" :key="`error-${item}`" class="validationItem bad">
            {{ item }}
          </div>
        </div>

        <div v-if="validationResult.warnings?.length" class="validationList">
          <div class="validationListTitle warn">警告</div>
          <div v-for="item in validationResult.warnings" :key="`warn-${item}`" class="validationItem warn">
            {{ item }}
          </div>
        </div>

        <div v-if="validationResult.provider_checks?.length" class="validationList">
          <div class="validationListTitle">Provider 连通性</div>
          <div class="probeList">
            <div v-for="probe in validationResult.provider_checks" :key="probe.provider" class="probeItem">
              <div class="probeHead">
                <div class="probeTitle">{{ probe.provider }}</div>
                <span class="probeBadge" :class="probe.ok ? 'ok' : (probe.skipped ? 'skip' : 'error')">
                  {{ probe.ok ? '成功' : (probe.skipped ? '已跳过' : '失败') }}
                </span>
              </div>
              <div class="probeMeta">模型：{{ probe.model || '未指定' }}</div>
              <div class="probeMessage">{{ probe.message }}</div>
            </div>
          </div>
        </div>

        <div class="previewGrid">
          <div class="previewCard">
            <div class="previewTitle">Provider 预览</div>
            <div v-if="!validationResult.preview?.providers?.length" class="emptySmall">暂无 provider 预览</div>
            <div v-else class="previewList">
              <div v-for="provider in validationResult.preview.providers" :key="provider.key" class="previewItem">
                <div class="previewItemHead">
                  <code>{{ provider.key }}</code>
                  <span class="previewMeta">{{ provider.model_count }} 个模型</span>
                </div>
                <div class="previewItemText">api_base：{{ provider.api_base || '未填写' }}</div>
                <div class="previewItemText">api_key：{{ provider.api_key_masked || '保留原值 / 未填写' }}</div>
                <div class="previewTags">
                  <span v-for="model in provider.models" :key="`${provider.key}-${model}`" class="previewTag">{{ model }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="previewCard">
            <div class="previewTitle">Skill 预览</div>
            <div class="previewItemText">搜索路径：{{ validationResult.preview?.skills?.paths?.length || 0 }} 个</div>
            <div class="previewItemText">已发现：{{ validationResult.preview?.skills?.discovered_count || 0 }} 个 skill</div>
            <div v-if="validationResult.preview?.skills?.discovered?.length" class="previewTags">
              <span
                v-for="skill in validationResult.preview.skills.discovered"
                :key="`preview-skill-${skill.name}`"
                class="previewTag"
              >
                {{ skill.name }}
              </span>
            </div>
            <div v-else class="emptySmall">当前未发现 skill</div>
          </div>

          <div class="previewCard">
            <div class="previewTitle">团队预览</div>
            <div v-if="!validationResult.preview?.teams?.length" class="emptySmall">暂无 team 预览</div>
            <div v-else class="previewList">
              <div v-for="team in validationResult.preview.teams" :key="team.key" class="previewItem">
                <div class="previewItemHead">
                  <code>{{ team.key }}</code>
                  <span class="previewMeta">{{ team.agent_count }} 个 Agent</span>
                </div>
                <div class="previewItemText">团队模型：{{ team.model || '继承默认 / 未指定' }}</div>
                <div class="previewItemText" v-if="team.description">描述：{{ team.description }}</div>
                <div class="previewAgents">
                  <div v-for="agent in team.agents" :key="`${team.key}-${agent.name || agent.model}`" class="previewAgent">
                    <span class="previewAgentName">{{ agent.name || '未命名 Agent' }}</span>
                    <span class="previewAgentMeta">{{ agent.model || '继承团队模型' }}</span>
                    <span class="previewAgentMeta">{{ agent.tool_count }} 个工具</span>
                    <span class="previewAgentMeta">{{ agent.skill_count }} 个 skill</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="previewCard previewCardWide">
            <div class="previewTitle">配置预览（敏感信息已脱敏）</div>
            <pre class="previewYaml">{{ validationResult.preview?.yaml_preview || '' }}</pre>
          </div>
        </div>
      </div>

      <div class="grid">
        <div class="mainColumn">
          <div class="card cardPrimary">
            <div class="cardTitle">智能体团队（teams）</div>

            <div class="teamWorkspace">
              <div class="teamRail">
                <div class="teamRailHead">
                  <div>
                    <div class="teamRailTitle">团队导航</div>
                    <div class="teamRailHint">先在这里选中一个 team，再编辑右侧内容。</div>
                  </div>
                  <button class="btn" type="button" @click="addTeam">新增 team</button>
                </div>

                <div class="teamList">
                  <button
                    v-for="(t, i) in teams"
                    :key="t.key"
                    type="button"
                    class="teamNavItem"
                    :class="{ active: selectedTeamIdx === i }"
                    @click="selectedTeamIdx = i"
                  >
                    <div class="teamNavHead">
                      <div class="teamNavName">{{ t.key }}</div>
                      <div class="teamNavMeta">{{ t.agents?.length || 0 }} Agent</div>
                    </div>
                    <div class="teamNavText">{{ t.description || '还没有填写团队描述' }}</div>
                  </button>
                </div>
              </div>

              <div v-if="currentTeam" class="teamEditor">
                <div class="teamForm">
                  <div class="teamOverview">
                    <div class="teamOverviewItem">
                      <div class="teamOverviewLabel">当前团队</div>
                      <div class="teamOverviewValue">{{ currentTeam.key || '未命名 team' }}</div>
                    </div>
                    <div class="teamOverviewItem">
                      <div class="teamOverviewLabel">Agent 数量</div>
                      <div class="teamOverviewValue">{{ currentTeam.agents.length }}</div>
                    </div>
                    <div class="teamOverviewItem">
                      <div class="teamOverviewLabel">final_output_agents</div>
                      <div class="teamOverviewValue">{{ splitListText(currentTeam.final_output_agents_text).length }}</div>
                    </div>
                  </div>

                  <div class="form">
                    <div class="row2">
                      <div class="row">
                        <label>team key</label>
                        <input v-model="currentTeam.key" placeholder="例如：custom_team" />
                      </div>
                      <div class="row">
                        <label>团队使用的 model</label>
                        <select v-model="currentTeam.model">
                          <option value="">（空=使用默认模型，但建议选一个）</option>
                          <option v-for="m in allModelNames" :key="m" :value="m">{{ m }}</option>
                        </select>
                      </div>
                    </div>

                    <div class="row2">
                      <div class="row">
                        <label>max_steps</label>
                        <input v-model="currentTeam.max_steps" type="number" placeholder="例如：100" />
                      </div>
                      <div class="row">
                        <label>final_output_agents（逗号分隔，可选）</label>
                        <input
                          v-model="currentTeam.final_output_agents_text"
                          placeholder="例如：Reviewer 或 Tester, Reviewer"
                        />
                      </div>
                    </div>

                    <div class="row">
                      <label>description</label>
                      <input v-model="currentTeam.description" placeholder="团队描述" />
                    </div>

                    <div class="row">
                      <label>rule（可选）</label>
                      <textarea v-model="currentTeam.rule" rows="3" placeholder="协作规则 / 流程约束"></textarea>
                    </div>
                  </div>

                  <div class="agentsHeader">
                    <div class="agentsTitle">Agents</div>
                    <button class="btn" type="button" @click="addAgent">新增 Agent</button>
                  </div>

                  <div v-if="currentTeam.agents.length === 0" class="emptySmall">暂无 agents。</div>

                  <div v-else class="agentWorkspace">
                    <div class="agentTabs">
                      <button
                        v-for="(a, idx) in currentTeam.agents"
                        :key="idx"
                        type="button"
                        class="agentTab"
                        :class="{ active: selectedAgentIdx === idx }"
                        @click="selectedAgentIdx = idx"
                      >
                        <span class="agentTabName">{{ a.name || `Agent #${idx + 1}` }}</span>
                        <span class="agentTabMeta">{{ a.modelOverride || currentTeam.model || '继承默认模型' }}</span>
                      </button>
                    </div>

                    <div v-if="currentAgent" class="agent">
                      <div class="agentHead">
                        <div class="agentTitle">
                          {{ currentAgent.name || `Agent #${selectedAgentIdx + 1}` }}
                        </div>
                        <button class="iconBtn danger" type="button" title="删除 agent" @click="removeAgent(selectedAgentIdx)">
                          删除
                        </button>
                      </div>

                      <div class="form">
                        <div class="row2">
                          <div class="row">
                            <label>name（必填）</label>
                            <input v-model="currentAgent.name" placeholder="例如：Planner" />
                          </div>
                          <div class="row">
                            <label>max_steps（可选）</label>
                            <input v-model="currentAgent.max_steps" type="number" placeholder="不填则继承团队默认/忽略" />
                          </div>
                        </div>

                        <div class="row">
                          <label>description</label>
                          <input v-model="currentAgent.description" placeholder="Agent 描述" />
                        </div>

                        <div class="row">
                          <label>system_prompt（必填）</label>
                          <textarea v-model="currentAgent.system_prompt" rows="4" placeholder="Agent 的系统提示词"></textarea>
                        </div>

                        <div class="row2">
                          <div class="row">
                            <label>tools（逗号分隔）</label>
                            <input v-model="currentAgent.toolsText" placeholder="例如：time, calculator, read, write" />
                          </div>
                          <div class="row">
                            <label>skills（逗号分隔）</label>
                            <input v-model="currentAgent.skillsText" placeholder="例如：researcher, writer" />
                          </div>
                        </div>

                        <div class="row2">
                          <div class="row">
                            <label>agent model（空=继承）</label>
                            <select v-model="currentAgent.modelOverride">
                              <option value="">继承团队 model</option>
                              <option v-for="m in allModelNames" :key="m" :value="m">{{ m }}</option>
                            </select>
                          </div>
                        </div>

                        <div v-if="availableSkills.length" class="row">
                          <label>快速选择 skills</label>
                          <div class="skillSelector">
                            <button
                              v-for="skill in availableSkills"
                              :key="`${currentAgent.name || selectedAgentIdx}-${skill.name}`"
                              type="button"
                              class="skillPill"
                              :class="{ active: hasAgentSkill(currentAgent, skill.name) }"
                              @click="toggleAgentSkill(currentAgent, skill.name)"
                            >
                              {{ skill.name }}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="majorSection">
              <div class="cardTitle">模型（models）</div>
              <div class="sectionHint">提示：`api_key` 不会回显到页面。输入为空表示“保留原值”。</div>

              <div v-if="providers.length === 0" class="emptySmall">暂无 provider，请先新增。</div>

              <div v-for="(p, idx) in providers" :key="p.key" class="provider">
                <div class="providerHead">
                  <div class="providerKey">
                    <code>{{ p.key }}</code>
                  </div>
                  <button class="iconBtn danger" type="button" title="删除 provider" :disabled="providers.length <= 1" @click="removeProvider(idx)">
                    删除
                  </button>
                </div>

                <div class="form">
                  <div class="row2">
                    <div class="row">
                      <label>api_base</label>
                      <input v-model="p.api_base" placeholder="例如：https://api.openai.com/v1" />
                    </div>
                    <div class="row">
                      <label>api_key（空=保留）</label>
                      <input v-model="p.api_key" placeholder="留空表示不修改" type="password" />
                    </div>
                  </div>

                  <div class="row">
                    <label>models（逗号分隔）</label>
                    <input v-model="p.modelsText" placeholder="例如：gpt-4o,gpt-4.1-mini" />
                  </div>
                </div>
              </div>

              <div class="addProvider">
                <div class="row2">
                  <div class="row">
                    <label>新增 provider key</label>
                    <input v-model="newProviderKey" placeholder="例如：openai 或 myprovider" />
                  </div>
                  <div class="row actions">
                    <button class="btn" type="button" @click="addProvider" :disabled="!newProviderKey.trim()">新增</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="sideColumn">
          <div class="card cardSidebar">
            <div class="sidebarIntro">
              <div class="cardTitle">能力包（skills）</div>
              <div class="sectionHint">侧栏用于维护 skill 搜索路径，并查看当前已经发现的能力包。</div>
            </div>

            <div class="skillSummary">
              <div class="skillSummaryItem">
                <div class="skillSummaryLabel">搜索路径</div>
                <div class="skillSummaryValue">{{ skillPathCount }}</div>
              </div>
              <div class="skillSummaryItem">
                <div class="skillSummaryLabel">已发现</div>
                <div class="skillSummaryValue">{{ availableSkills.length }}</div>
              </div>
            </div>

            <div class="form">
              <div class="row">
                <label>skills.paths（逗号或换行分隔）</label>
                <textarea
                  v-model="skillPathsText"
                  rows="4"
                  placeholder="例如：agentmesh/skills 或 ./custom_skills"
                ></textarea>
              </div>
            </div>

            <div class="previewTitle">当前已发现的 skills</div>
            <div v-if="availableSkills.length" class="skillCatalog skillCatalogSidebar">
              <div v-for="skill in availableSkills" :key="`available-${skill.name}`" class="skillCard">
                <div class="skillCardHead">
                  <div class="skillCardName">{{ skill.name }}</div>
                  <span class="skillCardMeta">{{ Array.isArray(skill.tools) ? skill.tools.length : 0 }} 个默认工具</span>
                </div>
                <div class="skillCardDesc">{{ skill.description || '暂无描述' }}</div>
                <div v-if="Array.isArray(skill.tools) && skill.tools.length" class="previewTags">
                  <span v-for="tool in skill.tools" :key="`${skill.name}-${tool}`" class="previewTag">
                    {{ tool }}
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="skillEmptyState">
              <div class="skillEmptyTitle">当前还没有发现任何 skill</div>
              <div class="skillEmptyText">可以先填写 `skills.paths`，然后点击“验证配置”或“保存到 config.yaml”刷新发现结果。</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { getApiBase } from '../composables/useApiBase'

const props = defineProps({
  embedded: { type: Boolean, default: false },
})

const emit = defineEmits(['saved'])

const loading = ref(false)
const saving = ref(false)
const validating = ref(false)
const notice = ref(null) // {type:'ok'|'error'|'info', text:string}
const validationResult = ref(null)

const providers = ref([]) // [{key, api_base, api_key, modelsText}]
const skillPathsText = ref('')
const availableSkills = ref([])
const teams = ref([]) // [{key, model, description, rule, max_steps, final_output_agents_text, agents:[...] }]
const selectedTeamIdx = ref(0)
const selectedAgentIdx = ref(0)

const newProviderKey = ref('')

const setNotice = (type, text) => {
  notice.value = { type, text }
  window.setTimeout(() => {
    if (notice.value?.text === text) notice.value = null
  }, 3500)
}

const allModelNames = computed(() => {
  const set = new Set()
  for (const p of providers.value) {
    const list = (p.modelsText || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    for (const m of list) set.add(m)
  }
  // Ensure currently selected team model is included (in case user saved invalid model last time).
  const t = currentTeam.value
  if (t?.model) set.add(t.model)
  for (const a of t?.agents || []) {
    if (a.modelOverride) set.add(a.modelOverride)
  }
  return Array.from(set)
})

const currentTeam = computed(() => teams.value[selectedTeamIdx.value] || null)
const currentAgent = computed(() => currentTeam.value?.agents?.[selectedAgentIdx.value] || null)

const splitListText = (text) => String(text || '')
  .split(/[\n,]/)
  .map((s) => s.trim())
  .filter(Boolean)

const skillPathCount = computed(() => splitListText(skillPathsText.value).length)
const totalAgentCount = computed(() => teams.value.reduce((sum, team) => sum + (Array.isArray(team?.agents) ? team.agents.length : 0), 0))

const joinListText = (values) => splitListText(Array.isArray(values) ? values.join(', ') : values).join(', ')

const hasAgentSkill = (agent, skillName) => splitListText(agent?.skillsText).includes(skillName)

const toggleAgentSkill = (agent, skillName) => {
  const next = new Set(splitListText(agent?.skillsText))
  if (next.has(skillName)) next.delete(skillName)
  else next.add(skillName)
  agent.skillsText = joinListText(Array.from(next))
}

const normalizeAgentForForm = (agent) => {
  const toolsArr = Array.isArray(agent?.tools) ? agent.tools : []
  const skillsArr = Array.isArray(agent?.skills) ? agent.skills : []
  return {
    name: String(agent?.name ?? ''),
    description: String(agent?.description ?? ''),
    system_prompt: String(agent?.system_prompt ?? ''),
    toolsText: toolsArr.join(', '),
    skillsText: skillsArr.join(', '),
    modelOverride: agent?.model ? String(agent.model) : '',
    max_steps: agent?.max_steps ?? null,
  }
}

const load = async () => {
  loading.value = true
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/config`)
    const json = await res.json().catch(() => null)
    if (!res.ok) {
      throw new Error(json?.detail || json?.message || `HTTP ${res.status}`)
    }

    const data = json?.data || {}

    const modelsObj = data?.models || {}
    providers.value = Object.entries(modelsObj).map(([key, p]) => ({
      key,
      api_base: p?.api_base || '',
      api_key: '', // do not show secrets; empty means "keep"
      modelsText: Array.isArray(p?.models) ? p.models.join(', ') : '',
    }))
    if (providers.value.length === 0) {
      providers.value = [{ key: 'openai', api_base: '', api_key: '', modelsText: '' }]
    }

    const skillsObj = data?.skills || {}
    skillPathsText.value = Array.isArray(skillsObj?.paths) ? skillsObj.paths.join('\n') : ''
    availableSkills.value = Array.isArray(data?.discovered_skills) ? data.discovered_skills : []

    const teamsObj = data?.teams || {}
    teams.value = Object.entries(teamsObj).map(([key, t]) => ({
      key,
      model: t?.model ? String(t.model) : '',
      description: String(t?.description ?? ''),
      rule: String(t?.rule ?? ''),
      max_steps: t?.max_steps ?? null,
      final_output_agents_text: Array.isArray(t?.final_output_agents)
        ? t.final_output_agents.map((x) => String(x || '').trim()).filter(Boolean).join(', ')
        : '',
      agents: Array.isArray(t?.agents) ? t.agents.map(normalizeAgentForForm) : [],
    }))
    if (teams.value.length === 0) {
      teams.value = [{
        key: 'custom_team',
        model: '',
        description: '',
        rule: '',
        max_steps: 100,
        final_output_agents_text: '',
        agents: [],
      }]
    }
    selectedTeamIdx.value = Math.min(selectedTeamIdx.value, teams.value.length - 1)
    setNotice('ok', '已加载配置')
  } catch (e) {
    setNotice('error', `加载失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

const validateBeforeSave = () => {
  if (providers.value.length === 0) throw new Error('models: 至少需要一个 provider')
  if (teams.value.length === 0) throw new Error('teams: 至少需要一个 team')

  for (const p of providers.value) {
    const key = (p.key || '').trim()
    if (!key) throw new Error('models: provider key 不能为空')
  }

  for (const t of teams.value) {
    if (!(t.key || '').trim()) throw new Error('teams: team key 不能为空')
    if (t.agents?.length) {
      for (const a of t.agents) {
        if (!(a.name || '').trim()) throw new Error('agents: agent.name 不能为空')
        if (!(a.system_prompt || '').trim()) throw new Error('agents: agent.system_prompt 不能为空')
      }
    }
  }
}

const buildSavePayload = () => {
  const models = {}
  for (const p of providers.value) {
    const modelsList = splitListText(p.modelsText)

    models[p.key] = {
      api_base: p.api_base,
      // empty means "keep"
      api_key: p.api_key || '',
      models: modelsList,
    }
  }

  const skills = {
    paths: splitListText(skillPathsText.value),
  }

  const teamsPayload = {}
  for (const t of teams.value) {
    const agentsPayload = (t.agents || []).map((a) => {
      const toolsList = splitListText(a.toolsText)
      const skillsList = splitListText(a.skillsText)

      const agentObj = {
        name: (a.name || '').trim(),
        description: a.description || '',
        system_prompt: a.system_prompt || '',
        tools: toolsList,
        skills: skillsList,
      }

      if ((a.modelOverride || '').trim()) agentObj.model = a.modelOverride
      if (a.max_steps !== null && a.max_steps !== '' && a.max_steps !== undefined) {
        const n = Number(a.max_steps)
        if (!Number.isNaN(n)) agentObj.max_steps = n
      }
      return agentObj
    })

    const teamObj = {
      model: t.model ? t.model : undefined,
      description: t.description || '',
      rule: t.rule || '',
      max_steps: t.max_steps !== null && t.max_steps !== '' && t.max_steps !== undefined ? Number(t.max_steps) : undefined,
      final_output_agents: (t.final_output_agents_text || '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      agents: agentsPayload,
    }

    // Remove undefined to avoid "max_steps: null" in YAML.
    Object.keys(teamObj).forEach((k) => {
      if (teamObj[k] === undefined) delete teamObj[k]
    })

    teamsPayload[t.key] = teamObj
  }

  return { models, skills, teams: teamsPayload }
}

const validateConfig = async () => {
  validating.value = true
  try {
    validateBeforeSave()
    const payload = buildSavePayload()

    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/config/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        include_connectivity: true,
      }),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(json?.detail || json?.message || `HTTP ${res.status}`)
    }
    validationResult.value = json?.data || null
    availableSkills.value = Array.isArray(validationResult.value?.preview?.skills?.discovered)
      ? validationResult.value.preview.skills.discovered
      : availableSkills.value
    if (validationResult.value?.ok) {
      setNotice('ok', '配置验证通过，可以保存。')
    } else {
      setNotice('info', '验证完成，请先处理错误或确认警告。')
    }
  } catch (e) {
    validationResult.value = null
    setNotice('error', `验证失败：${e?.message || e}`)
  } finally {
    validating.value = false
  }
}

const save = async () => {
  saving.value = true
  try {
    validateBeforeSave()
    const payload = buildSavePayload()

    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const json = await res.json().catch(() => ({}))

    if (!res.ok) {
      throw new Error(json?.detail || json?.message || `HTTP ${res.status}`)
    }

    await load()
    setNotice('ok', '已保存到 config.yaml')
    emit('saved')
  } catch (e) {
    setNotice('error', `保存失败：${e?.message || e}`)
  } finally {
    saving.value = false
  }
}

const addProvider = () => {
  const key = newProviderKey.value.trim()
  if (!key) return
  if (providers.value.some((p) => p.key === key)) {
    setNotice('info', `provider ${key} 已存在`)
    return
  }
  providers.value.push({
    key,
    api_base: '',
    api_key: '',
    modelsText: '',
  })
  newProviderKey.value = ''
}

const removeProvider = (idx) => {
  providers.value.splice(idx, 1)
}

const addTeam = () => {
  const baseKey = 'custom_team'
  let key = baseKey
  let i = 2
  while (teams.value.some((t) => t.key === key)) {
    key = `${baseKey}_${i++}`
  }
  teams.value.push({
    key,
    model: '',
    description: '',
    rule: '',
    max_steps: 100,
    final_output_agents_text: '',
      agents: [],
    })
  selectedTeamIdx.value = teams.value.length - 1
}

const addAgent = () => {
  if (!currentTeam.value) return
  currentTeam.value.agents.push({
    name: '',
    description: '',
    system_prompt: '',
    toolsText: '',
    skillsText: '',
    modelOverride: '',
    max_steps: null,
  })
  selectedAgentIdx.value = currentTeam.value.agents.length - 1
}

const removeAgent = (idx) => {
  if (!currentTeam.value) return
  currentTeam.value.agents.splice(idx, 1)
  const lastIdx = currentTeam.value.agents.length - 1
  selectedAgentIdx.value = Math.max(0, Math.min(selectedAgentIdx.value, lastIdx))
}

watch(currentTeam, (team) => {
  const count = Array.isArray(team?.agents) ? team.agents.length : 0
  const lastIdx = count - 1
  selectedAgentIdx.value = Math.max(0, Math.min(selectedAgentIdx.value, lastIdx))
}, { immediate: true })

onMounted(load)
</script>

<style scoped>
*,
*::before,
*::after {
  box-sizing: border-box;
}

.cfg {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: #ffffff;
}

.cfg.embedded {
  background: transparent;
}

.cfg.embedded .top {
  margin: 12px 12px 0;
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(16px);
}

.top {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.6);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title {
  font-weight: 800;
  color: #111827;
}

.sub {
  font-size: 12px;
  color: #6b7280;
}

.right {
  display: flex;
  align-items: center;
  gap: 10px;
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

.content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  flex: 1;
}

.workspaceStats {
  margin: 0 12px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.workspaceGuide {
  margin: 0 12px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.guideCard {
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  padding: 14px;
  display: grid;
  gap: 8px;
}

.guideLabel {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #69727e;
}

.guideValue {
  font-size: 20px;
  font-weight: 800;
  color: #222830;
}

.guideText {
  font-size: 12px;
  line-height: 1.6;
  color: #69727e;
}

.workspaceStat,
.teamOverviewItem {
  padding: 2px 0;
}

.workspaceStatLabel,
.teamOverviewLabel,
.teamRailHint,
.teamNavMeta,
.teamNavText {
  font-size: 12px;
  color: #69727e;
  line-height: 1.45;
}

.workspaceStatValue,
.teamOverviewValue {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 800;
  color: #222830;
}

.validationCard {
  margin: 0 12px;
  border: 1px solid rgba(37, 99, 235, 0.14);
  background: rgba(239, 246, 255, 0.7);
  border-radius: 14px;
  padding: 14px;
  display: grid;
  gap: 12px;
}

.validationHeader {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.validationTitle {
  font-size: 13px;
  font-weight: 800;
  color: #1e3a8a;
}

.validationSub {
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
  margin-top: 2px;
}

.validationBadge,
.probeBadge {
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
}

.validationBadge.ok,
.probeBadge.ok {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.validationBadge.error,
.probeBadge.error {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.probeBadge.skip {
  background: rgba(148, 163, 184, 0.16);
  color: #475569;
}

.validationSummary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.summaryItem {
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.85);
  border-radius: 12px;
  padding: 10px 12px;
}

.summaryLabel {
  font-size: 12px;
  color: #64748b;
}

.summaryValue {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  margin-top: 4px;
}

.validationList {
  display: grid;
  gap: 8px;
}

.validationListTitle {
  font-size: 12px;
  font-weight: 800;
  color: #0f172a;
}

.validationListTitle.bad {
  color: #b91c1c;
}

.validationListTitle.warn {
  color: #92400e;
}

.validationItem {
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.9);
}

.validationItem.bad {
  border: 1px solid rgba(239, 68, 68, 0.18);
  background: rgba(254, 242, 242, 0.9);
  color: #991b1b;
}

.validationItem.warn {
  border: 1px solid rgba(245, 158, 11, 0.18);
  background: rgba(255, 251, 235, 0.92);
  color: #92400e;
}

.probeList {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.probeItem {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  padding: 10px 12px;
  display: grid;
  gap: 6px;
}

.probeHead,
.previewItemHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.probeTitle,
.previewTitle {
  font-size: 12px;
  font-weight: 800;
  color: #0f172a;
}

.probeMeta,
.probeMessage,
.previewItemText,
.previewMeta,
.previewAgentMeta {
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}

.previewGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.previewCard {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  padding: 12px;
  display: grid;
  gap: 10px;
}

.previewCardWide {
  grid-column: 1 / -1;
}

.previewList,
.previewAgents {
  display: grid;
  gap: 8px;
}

.previewTags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.skillCatalog {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.skillCard {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(57, 120, 210, 0.16);
  background: rgba(250, 253, 255, 0.95);
  min-width: 0;
}

.skillCardHead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.skillCardName {
  font-size: 13px;
  font-weight: 800;
  color: #15467f;
  min-width: 0;
  overflow-wrap: anywhere;
}

.skillCardMeta,
.skillCardDesc {
  font-size: 12px;
  color: #5d7fa6;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.previewItem {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  padding-top: 8px;
}

.previewItem:first-child {
  border-top: none;
  padding-top: 0;
}

.previewTag {
  display: inline-flex;
  max-width: 100%;
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.previewAgent {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  border-top: 1px dashed rgba(0, 0, 0, 0.06);
  padding-top: 8px;
}

.previewAgent:first-child {
  border-top: none;
  padding-top: 0;
}

.previewAgentName {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.previewYaml {
  margin: 0;
  padding: 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.06);
  font-size: 12px;
  line-height: 1.55;
  color: #334155;
  overflow: auto;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.8fr);
  align-items: start;
  gap: 16px;
  padding: 12px;
  overflow: visible;
  min-height: 0;
  flex: 1;
}

.mainColumn,
.sideColumn {
  display: grid;
  gap: 16px;
  align-content: start;
  min-width: 0;
}

.card {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  padding: 16px;
  min-height: 120px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: auto;
  overflow: visible;
}

.cardPrimary {
  min-height: 0;
}

.cardSidebar {
  position: sticky;
  top: 12px;
  gap: 14px;
}

.cardTitle {
  font-size: 12px;
  font-weight: 800;
  color: #374151;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.sectionHint {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
  line-height: 1.5;
}

.sidebarIntro {
  display: grid;
  gap: 6px;
}

.skillSummary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.skillSummaryItem {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  background: rgba(249, 250, 251, 0.8);
  padding: 10px 12px;
}

.skillSummaryLabel {
  font-size: 12px;
  color: #6b7280;
}

.skillSummaryValue {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 800;
  color: #111827;
}

.skillCatalogSidebar {
  grid-template-columns: 1fr;
}

.skillEmptyState {
  border: 1px dashed rgba(27, 31, 38, 0.14);
  border-radius: 14px;
  background: rgba(249, 250, 251, 0.7);
  padding: 18px 16px;
  display: grid;
  gap: 8px;
}

.skillEmptyTitle {
  font-size: 13px;
  font-weight: 800;
  color: #1f2937;
}

.skillEmptyText {
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}

.form {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.row {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.row2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
}

label {
  font-size: 12px;
  font-weight: 700;
  color: #374151;
}

input,
textarea,
select {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  padding: 10px 10px;
  font-size: 13px;
  outline: none;
  background: white;
  color: #111827;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

textarea {
  resize: vertical;
}

input:focus,
textarea:focus,
select:focus {
  border-color: rgba(51, 112, 255, 0.6);
  box-shadow: 0 0 0 3px rgba(51, 112, 255, 0.12);
}

.emptySmall {
  font-size: 12px;
  color: #9ca3af;
}

.provider {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  padding-top: 10px;
  margin-top: 10px;
  min-width: 0;
}

.provider:first-of-type {
  border-top: none;
  padding-top: 0;
  margin-top: 0;
}

.providerHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  min-width: 0;
}

.providerKey code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  overflow-wrap: anywhere;
  word-break: break-all;
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

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

.addProvider {
  margin-top: auto;
  padding-top: 12px;
}

.teamPicker {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding-bottom: 12px;
  margin-bottom: 12px;
}

.teamForm {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.teamWorkspace {
  display: grid;
  grid-template-columns: minmax(240px, 0.72fr) minmax(0, 1.28fr);
  gap: 16px;
  min-width: 0;
}

.teamRail,
.teamEditor {
  min-width: 0;
}

.teamRail {
  display: grid;
  gap: 12px;
  align-content: start;
}

.teamRailHead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(27, 31, 38, 0.08);
}

.teamRailTitle {
  font-size: 12px;
  font-weight: 800;
  color: #222830;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.teamList {
  display: grid;
  gap: 8px;
}

.teamNavItem {
  width: 100%;
  text-align: left;
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  padding: 12px;
  display: grid;
  gap: 6px;
  cursor: pointer;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}

.teamNavItem:hover {
  border-color: rgba(27, 31, 38, 0.16);
  box-shadow: 0 12px 24px rgba(18, 22, 28, 0.06);
  transform: translateY(-1px);
}

.teamNavItem.active {
  border-color: rgba(74, 92, 118, 0.28);
  background: rgba(248, 250, 252, 0.96);
}

.teamNavHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.teamNavName {
  font-size: 13px;
  font-weight: 800;
  color: #222830;
  overflow-wrap: anywhere;
}

.teamEditor {
  display: grid;
  gap: 14px;
}

.teamOverview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.majorSection {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid rgba(27, 31, 38, 0.08);
  display: grid;
  gap: 10px;
}

.agentsHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.agentsTitle {
  font-size: 12px;
  font-weight: 800;
  color: #374151;
}

.agent {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  padding: 14px;
  background: rgba(249, 250, 251, 0.7);
  min-width: 0;
}

.agentWorkspace {
  display: grid;
  gap: 10px;
}

.agentTabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.agentTab {
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  padding: 8px 12px;
  display: grid;
  gap: 2px;
  text-align: left;
  cursor: pointer;
  min-width: 140px;
  max-width: 100%;
}

.agentTab:hover {
  border-color: rgba(27, 31, 38, 0.18);
  background: rgba(255, 255, 255, 0.96);
}

.agentTab.active {
  border-color: rgba(74, 92, 118, 0.28);
  background: rgba(74, 92, 118, 0.08);
}

.agentTabName {
  font-size: 12px;
  font-weight: 800;
  color: #222830;
  overflow-wrap: anywhere;
}

.agentTabMeta {
  font-size: 11px;
  color: #69727e;
  overflow-wrap: anywhere;
}

.agentHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.agentTitle {
  font-size: 12px;
  font-weight: 800;
  color: #374151;
}

.skillSelector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.skillPill {
  border: 1px solid rgba(57, 120, 210, 0.22);
  background: rgba(255, 255, 255, 0.92);
  color: #1d4f8f;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.skillPill:hover {
  border-color: rgba(52, 125, 224, 0.45);
  background: rgba(236, 246, 255, 0.98);
}

.skillPill.active {
  border-color: rgba(28, 92, 175, 0.42);
  background: linear-gradient(180deg, rgba(227, 241, 255, 1) 0%, rgba(210, 231, 255, 0.96) 100%);
  color: #164784;
}

/* Neutral office-workbench overrides */
.cfg {
  background: #ffffff;
}

.top {
  border-bottom-color: rgba(27, 31, 38, 0.08);
  background: #ffffff;
}

.title,
.validationTitle,
.cardTitle,
.agentsTitle,
.probeTitle,
.previewTitle,
.agentTitle,
.summaryValue,
.previewAgentName,
.validationListTitle,
label {
  color: #222830;
}

.sub,
.validationSub,
.summaryLabel,
.previewItemText,
.previewMeta,
.previewAgentMeta,
.sectionHint,
.emptySmall,
.loading {
  color: #69727e;
}

.notice,
.validationCard,
.previewCard,
.card,
.summaryItem,
.probeItem,
.agent,
.previewYaml,
.skillCard {
  border-color: rgba(27, 31, 38, 0.1);
  background: #ffffff;
  box-shadow: 0 12px 26px rgba(18, 22, 28, 0.05);
}

.notice {
  color: #414854;
}

.notice.info {
  border-color: rgba(74, 92, 118, 0.18);
  background: rgba(74, 92, 118, 0.08);
}

.previewYaml {
  color: #37404b;
  background: #ffffff;
}

input,
textarea,
select {
  border-color: rgba(27, 31, 38, 0.12);
  background: rgba(255, 255, 255, 0.88);
  color: #2c333d;
}

input:focus,
textarea:focus,
select:focus {
  border-color: rgba(74, 92, 118, 0.32);
  box-shadow: 0 0 0 3px rgba(74, 92, 118, 0.1);
}

.btn,
.iconBtn {
  border-color: rgba(27, 31, 38, 0.12);
  background: rgba(255, 255, 255, 0.8);
  color: #2b333e;
  box-shadow: none;
}

.btn:hover {
  border-color: rgba(27, 31, 38, 0.16);
  background: rgba(255, 255, 255, 0.94);
  color: #1f2329;
}

.provider,
.teamPicker,
.agentsHeader,
.previewItem,
.previewAgent {
  border-color: rgba(27, 31, 38, 0.08);
}

.previewTag,
.skillPill {
  border-color: rgba(27, 31, 38, 0.1);
  background: rgba(255, 255, 255, 0.82);
  color: #46525f;
}

.skillCardName {
  color: #232830;
}

.skillCardMeta,
.skillCardDesc {
  color: #69727e;
}

.skillPill:hover {
  border-color: rgba(27, 31, 38, 0.16);
  background: rgba(255, 255, 255, 0.96);
}

.skillPill.active {
  border-color: rgba(74, 92, 118, 0.28);
  background: rgba(74, 92, 118, 0.12);
  color: #263243;
}

.validationBadge.ok,
.probeBadge.ok {
  background: rgba(74, 92, 118, 0.12);
  color: #415369;
}

.content {
  animation: cfg-appear 0.4s ease both;
}

@keyframes cfg-appear {
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
  .validationSummary,
  .previewGrid,
  .grid,
  .skillSummary,
  .workspaceStats,
  .workspaceGuide,
  .teamWorkspace,
  .teamOverview {
    grid-template-columns: 1fr;
  }

  .cardSidebar {
    position: static;
  }

  .row2 {
    grid-template-columns: 1fr;
  }

  .skillCardHead {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
