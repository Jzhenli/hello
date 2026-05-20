<script setup lang="ts">
import { ref, computed, onMounted, markRaw, watch } from 'vue'
import { VueFlow, useVueFlow, type Connection, type NodeChange, type EdgeChange } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

import NodePalette from './NodePalette.vue'
import TriggerNode from './nodes/TriggerNode.vue'
import ScheduleTriggerNode from './nodes/ScheduleTriggerNode.vue'
import ConditionNode from './nodes/ConditionNode.vue'
import LogicNode from './nodes/LogicNode.vue'
import ActionNode from './nodes/ActionNode.vue'

import type { RuleNode, RuleEdge, RuleNodeData, NodeType } from '@/types/rule'
import { createNode, validateGraph, exportRule, importRule } from '@/utils/ruleConverter'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  ruleId?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { 
  onConnect, 
  onNodesChange, 
  onEdgesChange, 
  onNodeClick,
  addNodes, 
  addEdges, 
  removeNodes,
  project,
  fitView
} = useVueFlow()

const nodes = ref<RuleNode[]>([])
const edges = ref<RuleEdge[]>([])
const selectedNodeId = ref<string | null>(null)
const ruleName = ref('新规则')
const ruleDescription = ref('')

const nodeTypes = {
  trigger: markRaw(TriggerNode),
  'schedule-trigger': markRaw(ScheduleTriggerNode),
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
  }
}

const handleSave = () => {
  const result = validateGraph(nodes.value, edges.value)
  
  if (!result.valid) {
    ElMessage.error(result.errors[0])
    return
  }
  
  const rule = exportRule(nodes.value, edges.value)
  rule.name = ruleName.value
  rule.description = ruleDescription.value
  
  console.log('保存规则:', rule)
  ElMessage.success('规则保存成功！')
  emit('close')
}

const handleClear = () => {
  nodes.value = []
  edges.value = []
  selectedNodeId.value = null
}

onMounted(() => {
  setTimeout(() => fitView(), 100)
})

watch(() => props.ruleId, (newId) => {
  if (newId) {
    // Load existing rule
  } else {
    nodes.value = []
    edges.value = []
  }
}, { immediate: true })
</script>

<template>
  <div class="rule-editor-canvas">
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <el-input 
          v-model="ruleName" 
          placeholder="规则名称" 
          style="width: 200px"
        />
        <el-input 
          v-model="ruleDescription" 
          placeholder="规则描述" 
          style="width: 300px"
        />
      </div>
      <div class="toolbar-right">
        <span class="node-count">节点: {{ nodes.length }} | 连线: {{ edges.length }}</span>
        <el-button @click="handleClear">清空</el-button>
        <el-button type="primary" :disabled="!canSave" @click="handleSave">保存</el-button>
      </div>
    </div>
    
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
      
      <div v-if="selectedNode" class="config-panel">
        <div class="panel-header">
          <span>节点配置</span>
          <el-button type="danger" link size="small" @click="handleNodeDelete(selectedNode.id)">
            删除节点
          </el-button>
        </div>
        <NodeConfigPanel
          :node-id="selectedNode.id"
          :node-type="selectedNode.type as NodeType"
          :node-data="selectedNode.data"
          @update="handleNodeUpdate"
          @delete="handleNodeDelete"
        />
      </div>
      
      <div v-else class="empty-panel">
        <div class="empty-content">
          <span class="empty-icon">📝</span>
          <p>选择节点进行配置</p>
          <p class="hint">从左侧拖拽节点到画布</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rule-editor-canvas {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
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
  color: #7f8c8d;
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
  background: #fff;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  font-weight: 600;
  color: #2c3e50;
}

.empty-panel {
  width: 320px;
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
</style>
