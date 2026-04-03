<template>
  <div class="rag" :class="{ embedded: props.embedded }">
    <div class="top">
      <div>
        <div class="title">知识库上传（RAG）</div>
        <div class="sub">上传、标注、入库和历史管理都集中在这里，方便持续维护文档知识库。</div>
      </div>
      <div class="meta">
        <div class="viewSwitch metaControl" role="tablist" aria-label="知识库视图切换">
          <button type="button" class="viewTab" :class="{ active: viewMode === 'library' }" @click="viewMode = 'library'">
            文档入库
          </button>
          <button type="button" class="viewTab" :class="{ active: viewMode === 'ops' }" @click="viewMode = 'ops'">
            运维总览
          </button>
        </div>
        <span v-if="docId" class="pill metaControl">文档 ID：<code>{{ docId }}</code></span>
        <span v-if="status" class="pill metaControl">状态：<code>{{ formatStatus(status) }}</code></span>
        <button class="btn danger metaAction" :disabled="!docId || deletingDocument || loadingDocuments || loadingDocument" @click="deleteCurrentDocument">
          {{ deletingDocument ? '删除中…' : '彻底删除当前文档' }}
        </button>
        <button class="btn metaAction" :disabled="loadingDocuments || loadingDocument || loadingOps" @click="refreshAll">
          {{ loadingDocuments || loadingDocument || loadingOps ? '刷新中…' : '刷新列表' }}
        </button>
      </div>
    </div>

    <div v-if="notice" class="notice" :class="notice.type">{{ notice.text }}</div>

    <div class="workbenchGuide">
      <div class="guideCard">
        <div class="guideLabel">当前模式</div>
        <div class="guideValue">{{ viewMode === 'library' ? '文档入库' : '运维总览' }}</div>
        <div class="guideText">
          {{ viewMode === 'library'
            ? '围绕单篇文档完成上传、标注、切块和结果预览。'
            : '从 embedding 配置、索引健康和版本问题看整体知识库状态。' }}
        </div>
      </div>

      <div class="guideCard">
        <div class="guideLabel">当前文档</div>
        <div class="guideValue">{{ selectedDocument?.title || selectedDocument?.file_name || '未选择' }}</div>
        <div class="guideText">
          {{ selectedDocument
            ? `状态 ${formatStatus(selectedDocument.status)}，当前有效分块 ${selectedDocument.active_chunk_count}/${selectedDocument.chunk_total}。`
            : '先从左侧列表选中文档，右侧会切换成围绕当前文档的完整工作区。' }}
        </div>
      </div>

      <div class="guideCard">
        <div class="guideLabel">库内概况</div>
        <div class="guideValue">{{ documents.length }} 份文档</div>
        <div class="guideText">
          已入库 {{ indexedDocumentCount }} 份，当前 active chunk {{ opsStats.active_chunks || 0 }}，便于先看单篇再看整体。
        </div>
      </div>
    </div>

    <div class="gridMain">
      <div class="card docListCard">
        <div class="cardHead">
          <div class="cardTitle">文档列表 / 历史记录</div>
          <div class="cardHint">点击一条记录可继续标注、重新入库、查看分块效果或查看版本历史。</div>
        </div>
        <div class="docSummaryGrid">
          <div class="summaryMini">
            <div class="summaryMiniLabel">文档总数</div>
            <div class="summaryMiniValue">{{ documents.length }}</div>
          </div>
          <div class="summaryMini">
            <div class="summaryMiniLabel">已入库</div>
            <div class="summaryMiniValue">{{ indexedDocumentCount }}</div>
          </div>
        </div>
        <div v-if="loadingDocuments" class="empty">文档列表加载中…</div>
        <div v-else-if="documents.length === 0" class="empty">暂无文档，先上传一份试试。</div>
        <div v-else class="docList">
          <button
            v-for="doc in documents"
            :key="doc.document_id"
            type="button"
            class="docItem"
            :class="{ active: selectedDocumentId === doc.document_id }"
            @click="selectDocument(doc.document_id)"
          >
            <div class="docItemHead">
              <div class="docTitle">{{ doc.title || doc.file_name }}</div>
              <span class="statusTag" :class="doc.status">{{ formatStatus(doc.status) }}</span>
            </div>
            <div class="docMeta">{{ doc.file_name }}</div>
            <div class="docMeta">更新时间：{{ formatDateTime(doc.updated_at) }}</div>
            <div class="docMeta">切块：{{ doc.active_chunk_count }}/{{ doc.chunk_total }}</div>
            <div v-if="doc.tags?.length" class="docTags">
              <span v-for="tag in doc.tags" :key="`${doc.document_id}-${tag}`" class="docTag">{{ tag }}</span>
            </div>
          </button>
        </div>
      </div>

      <div class="card workflowCard">
        <div class="cardHead">
          <div class="cardTitle">{{ viewMode === 'library' ? '上传与标注' : '运维总览' }}</div>
          <div class="cardHint">
            {{
              viewMode === 'library'
                ? '当前支持 `.txt` / `.docx`，建议先上传解析，再补充元信息。'
                : '这里集中展示当前 embedding 配置、索引健康、重复文档和一键重建入口。'
            }}
          </div>
        </div>

        <template v-if="viewMode === 'library'">
          <div class="selectionBanner" :class="{ empty: !selectedDocument }">
            <div class="selectionBannerMain">
              <div class="selectionBannerLabel">当前工作文档</div>
              <div class="selectionBannerTitle">{{ selectedDocument?.title || selectedDocument?.file_name || '还没有选中文档' }}</div>
              <div class="selectionBannerText">
                {{
                  selectedDocument
                    ? `文件名：${selectedDocument.file_name}，最近更新时间 ${formatDateTime(selectedDocument.updated_at)}`
                    : '先上传文档或从左侧列表选择一条记录，右侧会围绕当前文档继续标注、切块和预览。'
                }}
              </div>
            </div>
            <div v-if="selectedDocument" class="selectionStats">
              <div class="selectionStat">
                <div class="selectionStatLabel">状态</div>
                <div class="selectionStatValue">{{ formatStatus(status) }}</div>
              </div>
              <div class="selectionStat">
                <div class="selectionStatLabel">段落预览</div>
                <div class="selectionStatValue">{{ previewParagraphs.length }}</div>
              </div>
              <div class="selectionStat">
                <div class="selectionStatLabel">分块</div>
                <div class="selectionStatValue">{{ chunkItems.length }}</div>
              </div>
            </div>
          </div>

          <div class="librarySteps">
            <div class="libraryFlow" role="tablist" aria-label="文档入库步骤">
              <button
                v-for="step in libraryFlowSteps"
                :key="step.key"
                type="button"
                class="flowStep"
                :class="{ active: activeLibraryStep === step.key, complete: step.complete, locked: step.locked }"
                :disabled="step.locked"
                :aria-selected="activeLibraryStep === step.key"
                @click="setActiveLibraryStep(step.key)"
              >
                <span class="flowStepCircle">{{ step.index }}</span>
                <span class="flowStepCopy">
                  <span class="flowStepEyebrow">{{ step.label }}</span>
                  <span class="flowStepTitle">{{ step.title }}</span>
                  <span class="flowStepHint">{{ step.hint }}</span>
                </span>
              </button>
            </div>

            <div class="flowPanelStatus">
              <div class="flowPanelStatusTitle">{{ activeLibraryStepMeta?.title || '上传文件' }}</div>
              <div class="flowPanelStatusText">{{ activeLibraryStepMeta?.panelHint || '按流程完成上传、标注与入库。' }}</div>
            </div>

            <div class="stepCard stepCard--panel">
              <template v-if="activeLibraryStep === 'upload'">
                <div class="stepHead">
                  <div>
                    <div class="stepEyebrow">Step 1</div>
                    <div class="sectionTitle">上传文件</div>
                  </div>
                  <div class="stepHint">支持 `.txt` / `.docx`，建议不超过 10MB。</div>
                </div>
                <input ref="fileInput" type="file" accept=".txt,.docx" @change="onSelectFile" />
                <div class="selectedFileHint">
                  {{ selectedFile ? `已选择：${selectedFile.name}` : '还没有选择文件' }}
                </div>
                <button class="primary" :disabled="uploading || !selectedFile" @click="uploadFile">
                  {{ uploading ? '上传中…' : '上传并解析' }}
                </button>
              </template>

              <template v-else-if="activeLibraryStep === 'annotate'">
                <div class="stepHead">
                  <div>
                    <div class="stepEyebrow">Step 2</div>
                    <div class="sectionTitle">补充标注</div>
                  </div>
                  <div class="stepHint">让文档在检索和回溯时更容易被识别。</div>
                </div>
                <div class="row">
                  <label>标题</label>
                  <input v-model="meta.title" placeholder="例如：产品手册 V1" />
                </div>
                <div class="row2">
                  <div class="row">
                    <label>分类</label>
                    <input v-model="meta.domain" placeholder="例如：产品 / 技术 / 流程" />
                  </div>
                  <div class="row">
                    <label>来源</label>
                    <input v-model="meta.source" placeholder="例如：内部文档库" />
                  </div>
                </div>
                <div class="row2">
                  <div class="row">
                    <label>版本</label>
                    <input v-model="meta.version" placeholder="例如：v1.0" />
                  </div>
                  <div class="row">
                    <label>标签（逗号分隔）</label>
                    <input v-model="tagsText" placeholder="例如：FAQ,流程,售后" />
                  </div>
                </div>
                <button class="btn" :disabled="!docId || savingAnno" @click="saveAnnotation">
                  {{ savingAnno ? '保存中…' : '保存标注' }}
                </button>
              </template>

              <template v-else>
                <div class="stepHead">
                  <div>
                    <div class="stepEyebrow">Step 3</div>
                    <div class="sectionTitle">切块入库</div>
                  </div>
                  <div class="stepHint">先调参数，再看下面的文本预览和分块预览是否自然。</div>
                </div>
                <div class="row2">
                  <div class="row">
                    <label>chunk_size</label>
                    <input v-model.number="chunkSize" type="number" min="200" max="2000" />
                    <div class="subHint">每个分块的目标长度，越大单块内容越多。</div>
                  </div>
                  <div class="row">
                    <label>overlap</label>
                    <input v-model.number="overlap" type="number" min="0" max="500" />
                    <div class="subHint">相邻分块重叠长度，帮助上下文衔接。</div>
                  </div>
                </div>
                <button class="primary" :disabled="!docId || ingesting" @click="ingestDoc">
                  {{ ingesting ? '入库中…' : '开始入库' }}
                </button>
                <div v-if="ingestResult" class="result resultGrid">
                  <div class="resultMini">
                    <div class="resultLabel">总切块</div>
                    <div class="resultValue">{{ ingestResult.chunk_total }}</div>
                  </div>
                  <div class="resultMini">
                    <div class="resultLabel">成功写入</div>
                    <div class="resultValue">{{ ingestResult.inserted }}</div>
                  </div>
                  <div class="resultMini">
                    <div class="resultLabel">失败</div>
                    <div class="resultValue">{{ ingestResult.failed }}</div>
                  </div>
                  <div class="resultMini">
                    <div class="resultLabel">状态</div>
                    <div class="resultValue">{{ formatStatus(ingestResult.status) }}</div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="section">
            <div class="sectionTitle">当前向量配置</div>
            <div class="metricGrid">
              <div class="metricCard">
                <div class="metricLabel">Active Profile</div>
                <div class="metricValue mono">{{ runtimeInfo.profile || '-' }}</div>
                <div class="metricMeta">{{ runtimeInfo.provider || 'unknown' }}</div>
              </div>
              <div class="metricCard metricCard--wide">
                <div class="metricLabel">Embedding Model</div>
                <div class="metricValue mono metricValue--small">{{ runtimeInfo.model || '-' }}</div>
                <div class="metricMeta">{{ runtimeInfo.api_base || '本地模型 / 无远程地址' }}</div>
              </div>
              <div class="metricCard">
                <div class="metricLabel">有效覆盖</div>
                <div class="metricValue">{{ coverageText }}</div>
                <div class="metricMeta">当前 active 记忆被现用模型覆盖的条目数</div>
              </div>
              <div class="metricCard">
                <div class="metricLabel">残留旧向量</div>
                <div class="metricValue">{{ opsStats.residual_non_current_embeddings_on_active || 0 }}</div>
                <div class="metricMeta">active 记忆上仍挂着旧模型 embedding</div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="sectionTitle">索引健康</div>
            <div v-if="loadingOps" class="empty">运维总览加载中…</div>
            <div v-else class="metricGrid">
              <div class="metricCard">
                <div class="metricLabel">知识库文档</div>
                <div class="metricValue">{{ opsStats.total_documents || 0 }}</div>
                <div class="metricMeta">indexed {{ opsStats.indexed_documents || 0 }} / uploaded {{ opsStats.uploaded_documents || 0 }}</div>
              </div>
              <div class="metricCard">
                <div class="metricLabel">知识块</div>
                <div class="metricValue">{{ opsStats.active_chunks || 0 }}</div>
                <div class="metricMeta">active / total {{ opsStats.total_chunks || 0 }}</div>
              </div>
              <div class="metricCard">
                <div class="metricLabel">Orphan Chunk</div>
                <div class="metricValue">{{ opsStats.orphan_doc_chunks || 0 }}</div>
                <div class="metricMeta">存在 active 记忆但已丢失 rag_chunks 映射</div>
              </div>
              <div class="metricCard">
                <div class="metricLabel">索引异常文档</div>
                <div class="metricValue">{{ opsStats.indexed_documents_without_active_chunks || 0 }}</div>
                <div class="metricMeta">状态为 indexed，但没有 active chunk</div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="sectionTitle">一键重建</div>
            <div class="hint">会先备份数据库，再迁移旧长期记忆、清 orphan chunk、补建缺失索引并按当前 embedding profile 重建 active 向量。</div>
            <div class="row2">
              <div class="row">
                <label>chunk_size</label>
                <input v-model.number="chunkSize" type="number" min="200" max="2000" />
              </div>
              <div class="row">
                <label>overlap</label>
                <input v-model.number="overlap" type="number" min="0" max="500" />
              </div>
            </div>
            <button class="primary" :disabled="rebuildingOps || loadingOps" @click="rebuildIndices">
              {{ rebuildingOps ? '重建中…' : '备份并重建索引' }}
            </button>
            <div v-if="lastRebuild" class="result">
              <div>备份文件：{{ lastRebuild.backup_files?.length || 0 }}</div>
              <div>迁移长期记忆：{{ lastRebuild.migrated_long_term_items || 0 }}</div>
              <div>清理 orphan chunk：{{ lastRebuild.deprecated_orphan_doc_chunks || 0 }}</div>
              <div>重建 embedding：{{ lastRebuild.rebuilt_embeddings || 0 }}</div>
              <div class="mono resultPath">{{ lastRebuild.backup_dir || '' }}</div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div class="gridPreview">
      <template v-if="viewMode === 'library'">
        <div class="card card--span2 inspectCard">
          <div class="inspectHead">
            <div class="cardHead">
              <div class="cardTitle">{{ inspectTab === 'text' ? '文本预览（前 20 段）' : '分块预览' }}</div>
              <div class="cardHint">
                {{
                  inspectTab === 'text'
                    ? '用于快速确认解析结果和段落边界是否合理。'
                    : '展示当前文档已生成的分块，方便判断 chunk_size / overlap 是否合适。'
                }}
              </div>
            </div>
            <div class="inspectTabs" role="tablist" aria-label="预览切换">
              <button type="button" class="inspectTab" :class="{ active: inspectTab === 'text' }" @click="inspectTab = 'text'">
                文本
              </button>
              <button type="button" class="inspectTab" :class="{ active: inspectTab === 'chunks' }" @click="inspectTab = 'chunks'">
                分块
              </button>
            </div>
          </div>
          <div v-if="loadingDocument" class="empty">文档详情加载中…</div>
          <template v-else-if="inspectTab === 'text'">
            <div v-if="previewParagraphs.length === 0" class="empty">暂无预览内容，请先上传或选择一份文档。</div>
            <div v-else class="preview">
              <div v-for="(p, idx) in previewParagraphs" :key="idx" class="para">
                <div class="idx">{{ idx + 1 }}</div>
                <div class="previewBlock">{{ p }}</div>
              </div>
            </div>
          </template>
          <template v-else>
            <div v-if="chunkItems.length === 0" class="empty">当前文档还没有分块结果，先执行“开始入库”。</div>
            <div v-else class="chunkList">
              <div v-for="chunk in chunkItems" :key="chunk.id" class="chunkItem">
                <div class="chunkHead">
                  <div class="chunkIndex">分块 #{{ chunk.chunk_index + 1 }}</div>
                  <div class="chunkMeta">{{ chunk.token_len }} 字符</div>
                </div>
                <div class="chunkContent">{{ chunk.content }}</div>
                <div class="chunkMeta">状态：{{ chunk.is_active ? '当前有效' : '历史版本' }}</div>
              </div>
            </div>
          </template>
        </div>
      </template>

      <template v-else>
        <div class="card">
          <div class="cardHead">
            <div class="cardTitle">模型分布</div>
            <div class="cardHint">用于确认当前 live 索引是否已经统一到 active embedding profile。</div>
          </div>
          <div v-if="loadingOps" class="empty">模型分布加载中…</div>
          <div v-else-if="modelDistribution.length === 0" class="empty">暂未检测到任何 embedding。</div>
          <div v-else class="opsStack">
            <div v-for="row in modelDistribution" :key="row.model" class="opsItem">
              <div class="opsItemHead">
                <div class="opsItemTitle mono">{{ row.model }}</div>
                <span class="statusTag" :class="row.is_active_model ? 'indexed' : 'uploaded'">
                  {{ row.is_active_model ? '当前模型' : '历史残留' }}
                </span>
              </div>
              <div class="docMeta">数量：{{ row.count }}，维度：{{ row.min_dim }}<template v-if="row.min_dim !== row.max_dim"> ~ {{ row.max_dim }}</template></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="cardHead">
            <div class="cardTitle">重复文档提示</div>
            <div class="cardHint">同内容文件会按 `file_hash` 复用已有记录；这里展示仍需人工关注的重复分组。</div>
          </div>
          <div v-if="loadingOps" class="empty">重复文档检测中…</div>
          <div v-else-if="duplicateGroups.length === 0" class="empty">
            当前没有检测到重复 `file_hash` 的文档。
            <div class="subHint">再次上传同一文件时，页面会直接提示复用来源文档，并跳转到原记录。</div>
          </div>
          <div v-else class="opsStack">
            <div v-for="group in duplicateGroups" :key="group.file_hash" class="opsItem">
              <div class="opsItemHead">
                <div class="opsItemTitle mono">{{ shortHash(group.file_hash) }}</div>
                <div class="docMeta">{{ group.count }} 条记录</div>
              </div>
              <div class="opsSubList">
                <div v-for="item in group.items" :key="item.document_id" class="opsSubItem">
                  <div class="opsInline">
                    <span class="docTitle">{{ item.title || item.file_name }}</span>
                    <span class="statusTag" :class="item.status">{{ formatStatus(item.status) }}</span>
                  </div>
                  <div class="docMeta">来源：{{ item.file_name }} / ID {{ item.document_id }} / 更新时间 {{ formatDateTime(item.updated_at) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card card--span2">
          <div class="cardHead">
            <div class="cardTitle">文档版本历史</div>
            <div class="cardHint">按当前选中文档的 `file_name` 聚合版本；也会额外列出最近存在多版本的文档组。</div>
          </div>
          <div v-if="loadingOps" class="empty">版本历史加载中…</div>
          <div v-else-if="documentHistory?.items?.length" class="opsStack">
            <div class="sectionHeader">
              <div class="sectionTitle">当前文档：{{ documentHistory.file_name }}</div>
              <div class="docMeta">共 {{ documentHistory.version_count }} 个版本</div>
            </div>
            <div class="opsSubList">
              <div v-for="item in documentHistory.items" :key="item.document_id" class="opsSubItem">
                <div class="opsInline">
                  <span class="docTitle">{{ item.title || item.file_name }}</span>
                  <span class="statusTag" :class="item.status">{{ formatStatus(item.status) }}</span>
                </div>
                <div class="docMeta">ID {{ item.document_id }} / hash {{ shortHash(item.file_hash) }} / chunk {{ item.active_chunk_count }}/{{ item.chunk_total }}</div>
                <div class="docMeta">更新时间：{{ formatDateTime(item.updated_at) }}</div>
              </div>
            </div>
          </div>
          <div v-else class="empty">
            当前所选文档还没有同名历史版本。
            <div v-if="versionGroups.length" class="subHint">下面这些文件存在多版本记录，可切换左侧文档查看详情。</div>
          </div>

          <div v-if="!loadingOps && versionGroups.length" class="opsStack opsStack--tight">
            <div class="sectionHeader">
              <div class="sectionTitle">最近存在多版本的文档组</div>
            </div>
            <div class="opsSubList">
              <div v-for="group in versionGroups" :key="group.file_name" class="opsSubItem">
                <div class="opsInline">
                  <span class="docTitle">{{ group.file_name }}</span>
                  <span class="docMeta">{{ group.count }} 个版本</span>
                </div>
                <div class="docMeta">最近更新：{{ formatDateTime(group.latest_updated_at) }}</div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { getApiBase } from '../composables/useApiBase'

const props = defineProps({
  embedded: { type: Boolean, default: false },
})

const fileInput = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const savingAnno = ref(false)
const ingesting = ref(false)
const loadingDocuments = ref(false)
const loadingDocument = ref(false)
const deletingDocument = ref(false)
const loadingOps = ref(false)
const rebuildingOps = ref(false)
const notice = ref(null)
const viewMode = ref('library')
const inspectTab = ref('text')
const activeLibraryStep = ref('upload')
const docId = ref(null)
const selectedDocumentId = ref(null)
const status = ref('')
const previewParagraphs = ref([])
const chunkItems = ref([])
const documents = ref([])
const chunkSize = ref(700)
const overlap = ref(100)
const ingestResult = ref(null)
const opsOverview = ref(null)
const lastRebuild = ref(null)

const meta = ref({
  title: '',
  domain: '',
  source: '',
  version: '',
})
const tagsText = ref('')

const tags = computed(() =>
  Array.from(
    new Set(
      (tagsText.value || '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    )
  )
)
const selectedDocument = computed(() => documents.value.find((item) => item.document_id === selectedDocumentId.value) || null)
const indexedDocumentCount = computed(() => documents.value.filter((item) => item.status === 'indexed').length)
const hasSelectedDocument = computed(() => Boolean(docId.value))
const hasAnnotationDraft = computed(() =>
  Boolean(
    meta.value.title?.trim() ||
    meta.value.domain?.trim() ||
    meta.value.source?.trim() ||
    meta.value.version?.trim() ||
    tags.value.length
  )
)
const libraryFlowSteps = computed(() => [
  {
    key: 'upload',
    index: '1',
    label: 'Step 1',
    title: '上传文件',
    hint: hasSelectedDocument.value ? '可继续上传新的来源文档' : '先把原始文件导入进来',
    panelHint: '选择本地文件并完成解析，后续步骤会自动解锁。',
    complete: hasSelectedDocument.value,
    locked: false,
  },
  {
    key: 'annotate',
    index: '2',
    label: 'Step 2',
    title: '补充标注',
    hint: hasSelectedDocument.value ? '补全标题、来源、标签等信息' : '上传后解锁',
    panelHint: '给文档补充结构化元信息，提升后续检索、筛选和版本追踪效果。',
    complete: hasSelectedDocument.value && hasAnnotationDraft.value,
    locked: !hasSelectedDocument.value,
  },
  {
    key: 'ingest',
    index: '3',
    label: 'Step 3',
    title: '切块入库',
    hint: hasSelectedDocument.value ? '调整参数后写入向量索引' : '上传后解锁',
    panelHint: '确认 chunk_size 和 overlap 后再入库，下面的文本与分块预览可以帮助校准效果。',
    complete: status.value === 'indexed' || chunkItems.value.length > 0,
    locked: !hasSelectedDocument.value,
  },
])
const activeLibraryStepMeta = computed(() => libraryFlowSteps.value.find((step) => step.key === activeLibraryStep.value) || libraryFlowSteps.value[0])

const runtimeInfo = computed(() => opsOverview.value?.runtime || {})
const opsStats = computed(() => opsOverview.value?.stats || {})
const modelDistribution = computed(() => (Array.isArray(opsOverview.value?.model_distribution) ? opsOverview.value.model_distribution : []))
const duplicateGroups = computed(() => (Array.isArray(opsOverview.value?.duplicate_groups) ? opsOverview.value.duplicate_groups : []))
const versionGroups = computed(() => (Array.isArray(opsOverview.value?.version_groups) ? opsOverview.value.version_groups : []))
const documentHistory = computed(() => opsOverview.value?.document_history || null)
const coverageText = computed(() => `${opsStats.value.active_model_coverage || 0}/${opsStats.value.active_memory_items || 0}`)

const setActiveLibraryStep = (stepKey) => {
  const target = libraryFlowSteps.value.find((step) => step.key === stepKey)
  if (!target || target.locked) return
  activeLibraryStep.value = stepKey
}

const syncLibraryStepForDocument = (doc) => {
  if (!doc?.document_id) {
    activeLibraryStep.value = 'upload'
    return
  }
  activeLibraryStep.value = doc?.status === 'indexed' ? 'ingest' : 'annotate'
}

const setNotice = (type, text) => {
  notice.value = { type, text }
  window.setTimeout(() => {
    if (notice.value?.text === text) notice.value = null
  }, 3500)
}

const formatDateTime = (value) => {
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value || '-'
  }
}

const shortHash = (value) => {
  const src = String(value || '').trim()
  if (!src) return '-'
  return src.length > 16 ? `${src.slice(0, 8)}...${src.slice(-6)}` : src
}

const formatStatus = (value) => {
  if (value === 'uploaded') return '已上传'
  if (value === 'indexed') return '已入库'
  if (value === 'failed') return '失败'
  return value || '未知'
}

const resetFormFromDocument = (doc) => {
  const metadata = doc?.metadata || {}
  meta.value = {
    title: metadata?.title || '',
    domain: metadata?.domain || '',
    source: metadata?.source || '',
    version: metadata?.version || '',
  }
  tagsText.value = Array.isArray(metadata?.tags) ? metadata.tags.join(', ') : ''
}

const populateDocumentState = (doc, chunks = []) => {
  selectedDocumentId.value = doc?.document_id || null
  docId.value = doc?.document_id || null
  status.value = doc?.status || ''
  previewParagraphs.value = Array.isArray(doc?.preview) ? doc.preview : []
  chunkItems.value = Array.isArray(chunks) ? chunks : []
  resetFormFromDocument(doc)
  syncLibraryStepForDocument(doc)
}

const loadOpsOverview = async (documentId = selectedDocumentId.value, quiet = false) => {
  loadingOps.value = true
  try {
    const base = getApiBase()
    const params = new URLSearchParams()
    if (documentId) params.set('document_id', String(documentId))
    params.set('history_limit', '20')
    const qs = params.toString()
    const res = await fetch(`${base}/api/v1/rag/ops/overview${qs ? `?${qs}` : ''}`)
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`)
    opsOverview.value = json?.data || null
  } catch (e) {
    if (!quiet) {
      setNotice('error', `加载运维总览失败：${e?.message || e}`)
    }
  } finally {
    loadingOps.value = false
  }
}

const loadDocuments = async (preferredDocumentId = null) => {
  loadingDocuments.value = true
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/rag/documents?limit=100&offset=0`)
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`)
    documents.value = Array.isArray(json?.data?.items) ? json.data.items : []

    const targetId =
      preferredDocumentId ||
      selectedDocumentId.value ||
      documents.value[0]?.document_id ||
      null
    if (targetId) {
      await loadDocumentDetail(targetId)
    } else {
      selectedDocumentId.value = null
      docId.value = null
      status.value = ''
      previewParagraphs.value = []
      chunkItems.value = []
      activeLibraryStep.value = 'upload'
      await loadOpsOverview(null, true)
    }
  } catch (e) {
    setNotice('error', `加载文档列表失败：${e?.message || e}`)
  } finally {
    loadingDocuments.value = false
  }
}

const loadDocumentDetail = async (documentId) => {
  if (!documentId) return
  loadingDocument.value = true
  try {
    const base = getApiBase()
    const [docRes, chunkRes] = await Promise.all([
      fetch(`${base}/api/v1/rag/${documentId}?include_paragraphs=true`),
      fetch(`${base}/api/v1/rag/${documentId}/chunks?limit=20&offset=0`),
    ])
    const docJson = await docRes.json().catch(() => ({}))
    const chunkJson = await chunkRes.json().catch(() => ({}))
    if (!docRes.ok) throw new Error(docJson?.detail || `HTTP ${docRes.status}`)
    if (!chunkRes.ok) throw new Error(chunkJson?.detail || `HTTP ${chunkRes.status}`)

    populateDocumentState(docJson?.data || {}, chunkJson?.data?.items || [])
    await loadOpsOverview(documentId, true)
  } catch (e) {
    setNotice('error', `加载文档详情失败：${e?.message || e}`)
  } finally {
    loadingDocument.value = false
  }
}

const refreshAll = async () => {
  await loadDocuments(selectedDocumentId.value)
}

const selectDocument = async (documentId) => {
  await loadDocumentDetail(documentId)
}

const onSelectFile = (e) => {
  const f = e.target.files?.[0]
  selectedFile.value = f || null
  if (f) activeLibraryStep.value = 'upload'
}

const uploadFile = async () => {
  if (!selectedFile.value) return
  const name = selectedFile.value.name || ''
  const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : ''
  if (!['txt', 'docx'].includes(ext)) {
    setNotice('error', '仅支持 .txt / .docx 文件')
    return
  }
  if (selectedFile.value.size > 10 * 1024 * 1024) {
    setNotice('error', '文件过大，请控制在 10MB 以内')
    return
  }
  uploading.value = true
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), 30000)
  try {
    const form = new FormData()
    form.append('file', selectedFile.value)
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/rag/upload`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`)
    const d = json?.data || {}
    selectedFile.value = null
    if (fileInput.value) fileInput.value.value = ''
    ingestResult.value = null
    await loadDocuments(d.document_id)
    activeLibraryStep.value = 'annotate'
    const sourceLabel = d?.title || d?.file_name || `文档 ${d?.document_id || ''}`
    setNotice('ok', d?.deduplicated ? `检测到重复文档，已复用来源「${sourceLabel}」（ID ${d?.document_id || '-'}）` : '上传并解析成功')
  } catch (e) {
    if (e?.name === 'AbortError') {
      setNotice('error', '上传超时，请检查后端服务是否可用')
    } else {
      setNotice('error', `上传失败：${e?.message || e}`)
    }
  } finally {
    window.clearTimeout(timer)
    uploading.value = false
  }
}

const saveAnnotation = async () => {
  if (!docId.value) return
  savingAnno.value = true
  try {
    const payload = {
      metadata: {
        ...meta.value,
        tags: tags.value,
      },
      paragraph_marks: [],
    }
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/rag/${docId.value}/annotate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`)
    await loadDocuments(docId.value)
    activeLibraryStep.value = 'ingest'
    setNotice('ok', '标注已保存')
  } catch (e) {
    setNotice('error', `标注保存失败：${e?.message || e}`)
  } finally {
    savingAnno.value = false
  }
}

const ingestDoc = async () => {
  if (!docId.value) return
  ingesting.value = true
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/rag/${docId.value}/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chunk_size: Number(chunkSize.value),
        overlap: Number(overlap.value),
      }),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`)
    ingestResult.value = json?.data || null
    await loadDocuments(docId.value)
    setNotice('ok', '入库完成')
  } catch (e) {
    setNotice('error', `入库失败：${e?.message || e}`)
  } finally {
    ingesting.value = false
  }
}

const rebuildIndices = async () => {
  const ok = window.confirm('确认执行“备份并重建索引”？这会备份数据库，并按照当前 embedding profile 重建 active 向量。')
  if (!ok) return

  rebuildingOps.value = true
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/rag/ops/rebuild`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chunk_size: Number(chunkSize.value),
        overlap: Number(overlap.value),
        skip_reindex: false,
      }),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`)
    lastRebuild.value = json?.data || null
    await loadDocuments(selectedDocumentId.value)
    setNotice('ok', '索引重建完成')
  } catch (e) {
    setNotice('error', `重建索引失败：${e?.message || e}`)
  } finally {
    rebuildingOps.value = false
  }
}

const deleteCurrentDocument = async () => {
  if (!docId.value) return
  const currentId = docId.value
  const current = documents.value.find((item) => item.document_id === currentId)
  const label = current?.title || current?.file_name || `ID ${currentId}`
  const ok = window.confirm(`确认彻底删除文档「${label}」？这会同时删除原文件、标注、分块和已入库向量，且不可恢复。`)
  if (!ok) return

  deletingDocument.value = true
  try {
    const base = getApiBase()
    const res = await fetch(`${base}/api/v1/rag/${currentId}`, {
      method: 'DELETE',
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`)

    ingestResult.value = null
    lastRebuild.value = null
    const remaining = documents.value.filter((item) => item.document_id !== currentId)
    const fallbackId = remaining[0]?.document_id || null
    await loadDocuments(fallbackId)
    setNotice('ok', '文档已彻底删除')
  } catch (e) {
    setNotice('error', `删除文档失败：${e?.message || e}`)
  } finally {
    deletingDocument.value = false
  }
}

onMounted(() => {
  loadDocuments()
})

watch(hasSelectedDocument, (ready) => {
  if (!ready && activeLibraryStep.value !== 'upload') {
    activeLibraryStep.value = 'upload'
  }
})
</script>

<style scoped>
.rag {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  overflow: auto;
  background: #ffffff;
}

.rag.embedded {
  background: transparent;
}

.rag.embedded .top {
  padding: 2px 2px 0;
}

.rag.embedded .card {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(14px);
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.title {
  font-size: 16px;
  font-weight: 700;
  color: #232830;
}
.sub {
  margin-top: 4px;
  font-size: 12px;
  color: #68717d;
  line-height: 1.45;
}
.meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: stretch;
  justify-content: flex-end;
}
.metaControl,
.metaAction {
  min-height: 42px;
  border-radius: 14px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
}
.viewSwitch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  border: 1px solid rgba(27, 31, 38, 0.1);
  background: rgba(255, 255, 255, 0.96);
}
.viewTab {
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #68717d;
  min-height: 34px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background .16s ease, color .16s ease;
  white-space: nowrap;
}
.viewTab.active {
  background: #111111;
  color: #ffffff;
}
.pill {
  border: 1px solid rgba(27, 31, 38, 0.1);
  padding: 0 16px;
  background: rgba(255,255,255,.85);
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  color: #2b333d;
}
.pill code {
  font: inherit;
  color: inherit;
  background: transparent;
}
.workbenchGuide {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.guideCard {
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  padding: 14px;
  display: grid;
  gap: 8px;
  box-shadow: 0 12px 24px rgba(18, 22, 28, 0.05);
}
.guideLabel {
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: #68717d;
}
.guideValue {
  font-size: 20px;
  line-height: 1.2;
  font-weight: 800;
  color: #232830;
  word-break: break-word;
}
.guideText {
  font-size: 12px;
  line-height: 1.6;
  color: #68717d;
}
.gridMain {
  display: grid;
  grid-template-columns: minmax(260px, 0.88fr) minmax(360px, 1.12fr);
  gap: 12px;
  align-items: start;
}
.gridPreview {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.card {
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 14px;
  background: #ffffff;
  padding: 12px;
  display: grid;
  gap: 10px;
  min-height: 0;
  box-shadow: 0 12px 24px rgba(18, 22, 28, 0.05);
}
.card--span2 {
  grid-column: span 2;
}
.cardHead {
  display: grid;
  gap: 4px;
}
.cardTitle {
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 800;
  color: #232830;
  letter-spacing: .04em;
}
.cardHint {
  font-size: 12px;
  color: #68717d;
  line-height: 1.45;
}
.docList {
  display: grid;
  gap: 8px;
  align-content: start;
  align-items: start;
  grid-auto-rows: max-content;
  max-height: 560px;
  overflow-y: auto;
  padding-right: 4px;
}
.docListCard {
  align-content: start;
}
.docSummaryGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.summaryMini,
.selectionStat,
.resultMini {
  padding: 2px 0;
  background: transparent;
}
.summaryMiniLabel,
.selectionStatLabel,
.resultLabel,
.stepEyebrow,
.selectedFileHint {
  font-size: 11px;
  line-height: 1.45;
  color: #68717d;
}
.summaryMiniValue,
.selectionStatValue,
.resultValue {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 800;
  color: #232830;
}
.docItem {
  text-align: left;
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 12px;
  background: #ffffff;
  padding: 10px;
  display: grid;
  gap: 6px;
  cursor: pointer;
  transition: border-color .15s ease, transform .15s ease, box-shadow .15s ease;
  box-shadow: 0 12px 24px rgba(18, 22, 28, 0.05);
}
.docItem:hover {
  border-color: rgba(27, 31, 38, 0.16);
  transform: translateY(-1px);
  box-shadow: 0 14px 26px rgba(18, 22, 28, 0.08);
}
.docItem.active {
  border-color: rgba(27, 31, 38, 0.2);
  background: #ffffff;
}
.docItemHead,
.chunkHead,
.opsItemHead,
.opsInline,
.sectionHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.docTitle,
.chunkIndex,
.opsItemTitle,
.sectionTitle,
label {
  font-size: 13px;
  font-weight: 700;
  color: #232830;
}
.docMeta,
.chunkMeta,
.hint,
.subHint,
.metricMeta,
.empty {
  font-size: 12px;
  color: #68717d;
  line-height: 1.45;
}
.docTags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.docTag {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(82, 101, 127, 0.14);
  color: #46586f;
  font-weight: 600;
}
.statusTag {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  font-weight: 700;
}
.statusTag.uploaded {
  background: rgba(82, 101, 127, 0.14);
  color: #46586f;
}
.statusTag.indexed {
  background: rgba(16,185,129,.12);
  color: #047857;
}
.statusTag.failed {
  background: rgba(239,68,68,.12);
  color: #b91c1c;
}
.workflowCard {
  align-content: start;
}
.selectionBanner {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(220px, 0.9fr);
  gap: 12px;
  padding: 4px 0 10px;
  border-bottom: 1px solid rgba(27, 31, 38, 0.08);
}
.selectionBanner.empty {
  grid-template-columns: 1fr;
}
.selectionBannerMain {
  display: grid;
  gap: 6px;
  min-width: 0;
}
.selectionBannerLabel {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .06em;
  font-weight: 800;
  color: #68717d;
}
.selectionBannerTitle {
  font-size: 18px;
  font-weight: 800;
  line-height: 1.2;
  color: #232830;
  overflow-wrap: anywhere;
}
.selectionBannerText {
  font-size: 12px;
  line-height: 1.5;
  color: #68717d;
}
.selectionStats,
.resultGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.librarySteps {
  display: grid;
  gap: 14px;
}
.libraryFlow {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.libraryFlow::before {
  content: '';
  position: absolute;
  left: calc(100% / 6);
  right: calc(100% / 6);
  top: 26px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(17, 17, 17, 0.12), rgba(255, 188, 117, 0.38), rgba(17, 17, 17, 0.12));
  z-index: 0;
}
.flowStep {
  position: relative;
  z-index: 1;
  text-align: left;
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(247, 248, 250, 0.96), rgba(255, 255, 255, 0.98));
  padding: 14px;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  cursor: pointer;
}
.flowStep.active {
  border-color: rgba(17, 17, 17, 0.24);
  box-shadow: 0 18px 32px rgba(17, 17, 17, 0.08);
  background: linear-gradient(180deg, rgba(255, 248, 239, 0.96), rgba(255, 255, 255, 0.98));
}
.flowStep.locked {
  opacity: .52;
  cursor: not-allowed;
  box-shadow: none;
}
.flowStepCircle {
  width: 52px;
  height: 52px;
  border-radius: 999px;
  border: 1.5px solid rgba(27, 31, 38, 0.14);
  background: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 800;
  color: #232830;
  box-shadow: inset 0 -6px 12px rgba(15, 23, 42, 0.04);
}
.flowStep.active .flowStepCircle {
  border-color: #111111;
  background: #ffffff;
  color: #232830;
}
.flowStepCopy {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.flowStepEyebrow {
  font-size: 11px;
  line-height: 1.35;
  color: #8b95a2;
  text-transform: uppercase;
  letter-spacing: .06em;
  font-weight: 800;
}
.flowStepTitle {
  font-size: 14px;
  line-height: 1.2;
  color: #232830;
  font-weight: 800;
}
.flowStepHint {
  font-size: 12px;
  line-height: 1.45;
  color: #68717d;
}
.flowPanelStatus {
  display: grid;
  gap: 4px;
  padding: 0 2px;
}
.flowPanelStatusTitle {
  font-size: 15px;
  font-weight: 800;
  color: #232830;
}
.flowPanelStatusText {
  font-size: 12px;
  line-height: 1.5;
  color: #68717d;
}
.stepCard {
  display: grid;
  gap: 12px;
}
.stepCard--panel {
  align-content: start;
  padding: 18px;
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(255, 232, 208, 0.44), transparent 34%),
    linear-gradient(180deg, rgba(252, 252, 251, 0.98), rgba(255, 255, 255, 0.98));
  box-shadow: 0 18px 32px rgba(18, 22, 28, 0.05);
}
.stepHead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.stepHint {
  max-width: 220px;
  font-size: 12px;
  line-height: 1.45;
  color: #68717d;
  text-align: right;
}
.selectedFileHint {
  margin-top: -2px;
}
.inspectCard {
  gap: 12px;
}
.inspectHead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.inspectTabs {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.85);
}
.inspectTab {
  border: none;
  border-radius: 999px;
  min-height: 32px;
  padding: 0 14px;
  background: transparent;
  color: #68717d;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.inspectTab.active {
  background: #111111;
  color: #ffffff;
}
.section {
  border-top: 1px solid rgba(27, 31, 38, 0.08);
  padding-top: 10px;
  display: grid;
  gap: 10px;
}
.section:first-of-type {
  border-top: none;
  padding-top: 0;
}
.row {
  display: grid;
  gap: 6px;
}
.row2,
.metricGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.metricCard {
  display: grid;
  gap: 6px;
  padding: 10px;
  border: 1px solid rgba(27, 31, 38, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.98);
}
.metricCard--wide {
  grid-column: span 2;
}
.metricLabel {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: #68717d;
  font-weight: 800;
}
.metricValue {
  font-size: 22px;
  line-height: 1.1;
  font-weight: 800;
  color: #232830;
}
.metricValue--small {
  font-size: 14px;
  line-height: 1.35;
  word-break: break-word;
}
.mono,
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
input,
textarea {
  border: 1px solid rgba(27, 31, 38, 0.12);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
  outline: none;
  background: rgba(255, 255, 255, 0.98);
  color: #2b333d;
}
input:focus,
textarea:focus {
  border-color: rgba(27, 31, 38, 0.22);
  box-shadow: 0 0 0 3px rgba(18, 22, 28, 0.08);
}
.btn {
  border: 1px solid rgba(27, 31, 38, 0.12);
  background: rgba(255, 255, 255, 0.86);
  color: #2b333d;
  padding: 0 18px;
  border-radius: 12px;
  min-height: 38px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
.btn.danger {
  border-color: rgba(239,68,68,.25);
  color: #b91c1c;
  background: rgba(254,242,242,.9);
}
.primary {
  border: none;
  border-radius: 10px;
  background: #111111;
  color: #fff;
  padding: 9px 12px;
  cursor: pointer;
  box-shadow: 0 10px 22px rgba(17, 17, 17, 0.22);
}
.btn:disabled,
.primary:disabled {
  opacity: .6;
  cursor: not-allowed;
}
.preview,
.chunkList,
.opsStack,
.docList,
.opsSubList {
  display: grid;
  gap: 8px;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-color: rgba(82, 101, 127, 0.42) rgba(0, 0, 0, 0.06);
}
.preview,
.chunkList {
  max-height: 420px;
}
.opsStack {
  max-height: 460px;
}
.opsStack--tight {
  max-height: none;
}
.para {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 8px;
  align-items: start;
}
.idx {
  font-size: 12px;
  color: #68717d;
  padding-top: 8px;
}
.previewBlock {
  min-height: 72px;
  border: 1px solid rgba(27, 31, 38, 0.08);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.85);
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.65;
  color: #334155;
  white-space: pre-wrap;
}
.chunkItem,
.opsItem,
.opsSubItem {
  border: 1px solid rgba(27, 31, 38, 0.1);
  border-radius: 12px;
  padding: 10px;
  background: #ffffff;
  display: grid;
  gap: 8px;
  box-shadow: 0 12px 24px rgba(18, 22, 28, 0.05);
}
.chunkContent {
  font-size: 13px;
  color: #334155;
  line-height: 1.55;
  white-space: pre-wrap;
}
.result {
  font-size: 13px;
  color: #374151;
  display: grid;
  gap: 4px;
}
.resultPath {
  word-break: break-all;
  color: #52657f;
}
.empty {
  padding: 20px 4px;
}
.notice {
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
  border: 1px solid rgba(27, 31, 38, 0.1);
}
.notice.ok {
  background: rgba(16,185,129,.1);
  border-color: rgba(16,185,129,.25);
}
.notice.error {
  background: rgba(239,68,68,.1);
  border-color: rgba(239,68,68,.25);
}
.gridMain,
.gridPreview {
  animation: rag-appear 0.4s ease both;
}

@keyframes rag-appear {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1180px) {
  .workbenchGuide,
  .gridMain,
  .gridPreview,
  .libraryFlow,
  .card--span2,
  .metricGrid,
  .selectionBanner {
    grid-template-columns: 1fr;
  }
  .card--span2 {
    grid-column: auto;
  }
  .metricCard--wide {
    grid-column: auto;
  }
  .libraryFlow::before {
    display: none;
  }
}
@media (max-width: 760px) {
  .top {
    flex-direction: column;
  }
  .meta {
    justify-content: flex-start;
  }
  .workbenchGuide,
  .row2 {
    grid-template-columns: 1fr;
  }
  .docSummaryGrid,
  .selectionStats,
  .resultGrid {
    grid-template-columns: 1fr;
  }
  .flowStep {
    grid-template-columns: 44px minmax(0, 1fr);
  }
  .flowStepCircle {
    width: 44px;
    height: 44px;
    font-size: 14px;
  }
  .stepHead {
    flex-direction: column;
  }
  .stepHint {
    max-width: none;
    text-align: left;
  }
  .inspectHead {
    flex-direction: column;
  }
}
</style>
