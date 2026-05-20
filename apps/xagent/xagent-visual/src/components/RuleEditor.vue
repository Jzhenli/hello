<script setup lang="ts">
import { ref, computed, onMounted, markRaw } from 'vue'
import { VueFlow, useVueFlow, type Connection, type NodeChange, type EdgeChange } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

import NodePalette from './NodePalette.vue'
import EditorToolbar from './EditorToolbar.vue'
import NodeConfigPanel from './NodeConfigPanel.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import Toast from './Toast.vue'
import TriggerNode from './nodes/TriggerNode.vue'
import ConditionNode from './nodes/ConditionNode.vue'
import LogicNode from './nodes/LogicNode.vue'
import ActionNode from './nodes/ActionNode.vue'

import type { RuleNode, RuleEdge, Rule, RuleNodeData, NodeType } from '@/types/rule'
import { 
  createNode, 
  validateGraph, 
  exportRule, 
  importRule, 
  createDefaultRule 
} from '@/utils/ruleConverter'
import { useResponsive } from '@/utils/useResponsive'

const { 
  onConnect, 
  onNodesChange, 
  onEdgesChange, 
  onNodeClick,
  addNodes, 
  addEdges, 
  removeNodes,
  removeEdges,
  project,
  getNodes,
  getEdges,
  fitView
} = useVueFlow()

const { isTablet, isMobile } = useResponsive()

const nodes = ref<RuleNode[]>([])
const edges = ref<RuleEdge[]>([])
const selectedNodeId = ref<string | null>(null)
const currentRule = ref<Rule | null>(null)

const showConfirm = ref(false)
const confirmMessage = ref('')
const confirmCallback = ref<(() => void) | null>(null)

const toastMessage = ref('')
const toastType = ref<'success' | 'error' | 'warning' | 'info'>('info')
const showToast = ref(false)

const isDrawerOpen = ref(false)

const nodeTypes = {
  trigger: markRaw(TriggerNode),
  condition: markRaw(ConditionNode),
  logic: markRaw(LogicNode),
  action: markRaw(ActionNode)
}

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  return nodes.value.find(n => n.id === selectedNodeId.value) || null
})

const canSave = computed(() => {
  const result = validateGraph(nodes.value, edges.value)
  return result.valid
})

const showConfigPanel = computed(() => !isTablet.value && !isMobile.value)
const showConfigDrawer = computed(() => isTablet.value || isMobile.value)

const showMessage = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => {
    showToast.value = false
  }, 3000)
}

const confirm = (message: string): Promise<boolean> => {
  return new Promise((resolve) => {
    confirmMessage.value = message
    showConfirm.value = true
    confirmCallback.value = () => resolve(true)
  })
}

const handleConfirmOk = () => {
  showConfirm.value = false
  if (confirmCallback.value) {
    confirmCallback.value()
    confirmCallback.value = null
  }
}

const handleConfirmCancel = () => {
  showConfirm.value = false
  confirmCallback.value = null
}

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
        isDrawerOpen.value = false
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
  if (showConfigDrawer.value) {
    isDrawerOpen.value = true
  }
})

const handleNodeUpdate = (data: RuleNodeData) => {
  if (!selectedNodeId.value) return
  
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
    isDrawerOpen.value = false
  }
}

const handleSave = () => {
  const result = validateGraph(nodes.value, edges.value)
  
  if (!result.valid) {
    showMessage(result.errors[0], 'error')
    return
  }
  
  currentRule.value = exportRule(nodes.value, edges.value)
  
  const json = JSON.stringify(currentRule.value, null, 2)
  console.log('保存规则:', json)
  
  showMessage('规则保存成功！', 'success')
  
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `rule-${currentRule.value.id}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const handleClear = async () => {
  const confirmed = await confirm('确定要清空画布吗？')
  
  if (confirmed) {
    nodes.value = []
    edges.value = []
    selectedNodeId.value = null
    currentRule.value = null
    isDrawerOpen.value = false
    showMessage('画布已清空', 'success')
  }
}

const handleExport = () => {
  if (nodes.value.length === 0) {
    showMessage('画布为空，无法导出', 'warning')
    return
  }
  
  const rule = exportRule(nodes.value, edges.value)
  const json = JSON.stringify(rule, null, 2)
  
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `rule-${rule.id}.json`
  a.click()
  URL.revokeObjectURL(url)
  
  showMessage('规则已导出', 'success')
}

const handleImport = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return
    
    try {
      const text = await file.text()
      const rule: Rule = JSON.parse(text)
      
      if (!rule.graph || !rule.graph.nodes) {
        throw new Error('无效的规则文件格式')
      }
      
      const imported = importRule(rule)
      nodes.value = imported.nodes
      edges.value = imported.edges
      currentRule.value = rule
      
      setTimeout(() => fitView(), 100)
      showMessage('规则导入成功', 'success')
    } catch (error) {
      showMessage('导入失败：' + (error as Error).message, 'error')
    }
  }
  
  input.click()
}

const closeDrawer = () => {
  isDrawerOpen.value = false
}

onMounted(() => {
  const defaultRule = createDefaultRule()
  nodes.value = defaultRule.nodes
  edges.value = defaultRule.edges
  
  setTimeout(() => fitView(), 100)
})
</script>

<template>
  <div class="rule-editor">
    <EditorToolbar
      :rule="currentRule"
      :can-save="canSave"
      @save="handleSave"
      @clear="handleClear"
      @export="handleExport"
      @import="handleImport"
    />
    
    <div class="editor-main">
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
      
      <template v-if="showConfigPanel">
        <NodeConfigPanel
          v-if="selectedNode"
          :node-id="selectedNode.id"
          :node-type="selectedNode.type as NodeType"
          :node-data="selectedNode.data"
          @update="handleNodeUpdate"
          @delete="handleNodeDelete"
        />
        
        <div v-else class="empty-panel">
          <div class="empty-content">
            <span class="empty-icon">📝</span>
            <p>选择节点进行配置</p>
            <p class="hint">点击画布中的节点查看详细配置</p>
          </div>
        </div>
      </template>

      <el-drawer
        v-if="showConfigDrawer"
        v-model="isDrawerOpen"
        direction="rtl"
        title="节点配置"
        size="320px"
        class="config-drawer"
        :with-header="true"
      >
        <NodeConfigPanel
          v-if="selectedNode"
          :node-id="selectedNode.id"
          :node-type="selectedNode.type as NodeType"
          :node-data="selectedNode.data"
          @update="handleNodeUpdate"
          @delete="handleNodeDelete"
        />
      </el-drawer>
    </div>
    
    <ConfirmDialog
      v-if="showConfirm"
      :message="confirmMessage"
      @ok="handleConfirmOk"
      @cancel="handleConfirmCancel"
    />
    
    <Toast
      v-if="showToast"
      :message="toastMessage"
      :type="toastType"
    />
  </div>
</template>

<style scoped>
.rule-editor {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
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

.empty-panel {
  width: 280px;
  background: #fff;
  border-left: 1px solid #e0e0e0;
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
  color: #2c3e50;
}

.empty-content .hint {
  font-size: 12px;
  color: #95a5a6;
}

.config-drawer :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 16px 20px;
  border-bottom: 1px solid #e0e0e0;
}

.config-drawer :deep(.el-drawer__body) {
  padding: 0;
  overflow-y: auto;
}

@media (max-width: 1024px) {
  .rule-editor {
    height: calc(100vh - 60px);
  }
  
  .empty-panel {
    width: 240px;
  }
}

@media (max-width: 768px) {
  .rule-editor {
    height: calc(100vh - 50px);
  }
}
</style>
