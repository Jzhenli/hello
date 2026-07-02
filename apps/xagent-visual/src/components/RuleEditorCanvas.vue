<template>
  <div class="rule-editor-canvas">
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <el-input 
          v-model="ruleName" 
          :placeholder="t('ruleEditor.ruleName')" 
          style="width: 200px"
        />
        <el-input 
          v-model="ruleDescription" 
          :placeholder="t('ruleEditor.ruleDescription')" 
          style="width: 300px"
        />
      </div>
      <div class="toolbar-right">
        <span class="node-count">{{ t('ruleEditor.nodeCount') }}: {{ nodes.length }} | {{ t('ruleEditor.edgeCount') }}: {{ edges.length }}</span>
        <el-button @click="handleClear" :disabled="loading">{{ t('ruleEditor.clear') }}</el-button>
        <el-button type="primary" :disabled="!canSave" :loading="saving" @click="handleSave">
          {{ saving ? t('ruleEditor.saving') : t('ruleEditor.save') }}
        </el-button>
      </div>
    </div>
    
    <div v-if="loading" class="editor-loading">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span>{{ t('ruleEditor.loadingRule') }}</span>
    </div>

    <div v-else class="editor-main">
      <NodePalette @drag-start="onDragStart" />
      
      <div class="editor-canvas" @drop="onDrop" @dragover="onDragOver">
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :node-types="nodeTypes"
          :default-edge-options="{ type: 'smoothstep', animated: true }"
          :fit-view-on-init="true"
          :snap-to-grid="true"
          :snap-grid="[15, 15]"
          class="vue-flow-container"
        >
          <Background pattern-color="#aaa" :gap="20" />
          <Controls />
          <MiniMap />
        </VueFlow>
      </div>
      
      <div v-if="selectedNode" class="config-panel">
        <div class="panel-header">
          <span>{{ t('ruleEditor.nodeConfig') }}</span>
          <el-button type="danger" link size="small" @click="handleNodeDelete(selectedNode.id)">
            {{ t('ruleEditor.deleteNode') }}
          </el-button>
        </div>
        <NodeConfigPanel
          :node-id="selectedNode.id"
          :node-type="selectedNode.type as NodeType"
          :node-data="selectedNode.data ?? {}"
          @update="handleNodeUpdate"
          @delete="handleNodeDelete"
        />
      </div>
      
      <div v-else class="empty-panel">
        <div class="empty-content">
          <span class="empty-icon">📝</span>
          <p>{{ t('ruleEditor.selectNodeHint') }}</p>
          <p class="hint">{{ t('ruleEditor.dragHint') }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, markRaw, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { VueFlow, useVueFlow, type Connection, type NodeChange, type EdgeChange } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

import NodePalette from './NodePalette.vue'
import NodeConfigPanel from './NodeConfigPanel.vue'
import TriggerNode from './nodes/TriggerNode.vue'
import ScheduleTriggerNode from './nodes/ScheduleTriggerNode.vue'
import ConditionNode from './nodes/ConditionNode.vue'
import LogicNode from './nodes/LogicNode.vue'
import ActionNode from './nodes/ActionNode.vue'
import NotificationNode from './nodes/NotificationNode.vue'

import type { RuleNode, RuleEdge, RuleNodeData, NodeType } from '@/types/rule'
import { createNode, validateGraph } from '@/utils/ruleConverter'
import { graphToBackendCreate, graphToBackendUpdate, backendToGraph } from '@/utils/ruleBridge'
import { useRuleStore } from '@/stores/rules'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'

const { t } = useI18n()

const props = defineProps<{
  ruleId?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const ruleStore = useRuleStore()

const { 
  onConnect, 
  onNodesChange, 
  onEdgesChange, 
  onNodeClick,
  addNodes, 
  addEdges, 
  removeNodes,
  findNode,
  project,
  fitView
} = useVueFlow()

const nodes = ref<RuleNode[]>([])
const edges = ref<RuleEdge[]>([])
const selectedNodeId = ref<string | null>(null)
const ruleName = ref(t('ruleEditor.defaultRuleName'))
const ruleDescription = ref('')
const saving = ref(false)
const loading = ref(false)

const nodeTypes = {
  trigger: markRaw(TriggerNode),
  'schedule-trigger': markRaw(ScheduleTriggerNode),
  condition: markRaw(ConditionNode),
  logic: markRaw(LogicNode),
  action: markRaw(ActionNode),
  notification: markRaw(NotificationNode)
} as any

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  const node = findNode(selectedNodeId.value)
  if (!node) return null
  return {
    id: node.id,
    type: node.type as NodeType,
    data: (node.data ?? {}) as RuleNodeData,
    position: node.position,
  }
})

const canSave = computed(() => {
  if (saving.value) return false
  const result = validateGraph(nodes.value, edges.value)
  return result.valid
})

const onDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/vueflow') as NodeType
  
  if (!type) return
  
  const { left, top } = (event.target as HTMLElement).getBoundingClientRect()
  const position = project({
    x: event.clientX - left,
    y: event.clientY - top
  })
  
  const newNode = createNode(type, position)
  addNodes([newNode])
}

const onDragStart = (type: NodeType, event: DragEvent) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', type)
    event.dataTransfer.effectAllowed = 'move'
  }
}

onConnect((params: Connection) => {
  addEdges([{
    ...params,
    type: 'smoothstep',
    animated: true
  }])
})

onNodesChange((changes: NodeChange[]) => {
  changes.forEach(change => {
    if (change.type === 'remove') {
      nodes.value = nodes.value.filter(n => n.id !== change.id)
      if (selectedNodeId.value === change.id) {
        selectedNodeId.value = null
      }
    }
  })
})

onEdgesChange((changes: EdgeChange[]) => {
  changes.forEach(change => {
    if (change.type === 'remove') {
      edges.value = edges.value.filter(e => e.id !== change.id)
    }
  })
})

onNodeClick(({ node }) => {
  selectedNodeId.value = node.id
  const nodeIndex = nodes.value.findIndex(n => n.id === node.id)
  if (nodeIndex !== -1 && node.data) {
    const currentData = nodes.value[nodeIndex].data || {}
    nodes.value[nodeIndex] = {
      ...nodes.value[nodeIndex],
      data: { ...currentData, ...node.data }
    }
  }
})

const handleNodeUpdate = (data: RuleNodeData) => {
  if (!selectedNodeId.value) return
  
  const node = findNode(selectedNodeId.value)
  if (node) {
    node.data = { ...data }
  }

  const nodeIndex = nodes.value.findIndex(n => n.id === selectedNodeId.value)
  if (nodeIndex !== -1) {
    nodes.value[nodeIndex] = {
      ...nodes.value[nodeIndex],
      data: { ...data }
    }
  }
}

const handleNodeDelete = (nodeId: string) => {
  removeNodes([nodeId])
  if (selectedNodeId.value === nodeId) {
    selectedNodeId.value = null
  }
}

const handleSave = async () => {
  const currentNodes = nodes.value.map(n => {
    const vfNode = findNode(n.id)
    return vfNode ? { ...n, data: vfNode.data as RuleNodeData } : n
  })

  const result = validateGraph(currentNodes, edges.value)
  
  if (!result.valid) {
    ElMessage.error(result.errors[0])
    return
  }
  
  saving.value = true
  
  try {
    if (props.ruleId) {
      const currentRule = ruleStore.rules.find(r => r.id === props.ruleId)
      const updateData = graphToBackendUpdate(
        ruleName.value,
        ruleDescription.value,
        currentNodes,
        edges.value,
        currentRule?.enabled ?? true
      )
      await ruleStore.updateRule(props.ruleId, updateData)
      ElMessage.success(t('ruleEditor.ruleSaved'))
    } else {
      const createData = graphToBackendCreate(
        ruleName.value,
        ruleDescription.value,
        currentNodes,
        edges.value
      )
      await ruleStore.createRule(createData)
      ElMessage.success(t('ruleEditor.ruleCreated'))
    }
    emit('saved')
    emit('close')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    const msg = detail
      ? (Array.isArray(detail) ? detail.map((d: any) => d.msg || d).join('; ') : String(detail))
      : t('ruleEditor.saveFailed')
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const handleClear = () => {
  nodes.value = []
  edges.value = []
  selectedNodeId.value = null
}

const loadRule = async (ruleId: string) => {
  loading.value = true
  try {
    const ruleResponse = await ruleStore.getRule(ruleId)
    if (!ruleResponse) {
      ElMessage.error(t('ruleEditor.ruleNotFound'))
      return
    }

    const graphData = backendToGraph(ruleResponse)
    if (graphData) {
      nodes.value = graphData.nodes
      edges.value = graphData.edges
      ruleName.value = graphData.name
      ruleDescription.value = graphData.description
      setTimeout(() => fitView(), 100)
    } else {
      ElMessage.warning(t('ruleEditor.parseFailed'))
    }
  } catch (e: any) {
    ElMessage.error(t('ruleEditor.loadFailed') + '：' + (e.message || t('common.unknownError')))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (props.ruleId) {
    loadRule(props.ruleId)
  } else {
    setTimeout(() => fitView(), 100)
  }
})

watch(() => props.ruleId, (newId) => {
  if (newId) {
    loadRule(newId)
  } else {
    nodes.value = []
    edges.value = []
    ruleName.value = t('ruleEditor.defaultRuleName')
    ruleDescription.value = ''
  }
}, { immediate: false })
</script>

<style scoped>
.rule-editor-canvas {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-container);
  border-bottom: 1px solid var(--border-base);
}

.toolbar-left {
  display: flex;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.node-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.editor-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 14px;
}

.editor-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.editor-canvas {
  flex: 1;
  position: relative;
}

.vue-flow-container {
  width: 100%;
  height: 100%;
}

.config-panel {
  width: 320px;
  background: var(--bg-container);
  border-left: 1px solid var(--border-base);
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-base);
  font-weight: 600;
  color: var(--text-primary);
}

.empty-panel {
  width: 320px;
  background: var(--bg-container);
  border-left: 1px solid var(--border-base);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
  padding: 20px;
}

.empty-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 12px;
}

.empty-content p {
  margin: 4px 0;
  color: var(--text-primary);
}

.empty-content .hint {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
