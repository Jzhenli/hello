import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ScadaPanel, ScadaComponent, ComponentType, PanelType, PointBinding } from '@/types/scada'
import { COMPONENT_TEMPLATES } from '@/types/scada'

function generateId(): string {
  return `comp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

// 生成样例面板数据
function generateSamplePanels(): ScadaPanel[] {
  const panelNames = [
    '暖通空调监控', '电力监控', '给排水监控', '照明控制', '电梯监控',
    '消防报警', '安防监控', '能耗分析', '环境监测', '停车场管理',
    '门禁管理', '视频监控', '新风系统', '冷站监控', '热站监控',
    '变配电监控', 'UPS监控', '发电机监控', '太阳能监控', '风能监控',
    '空气质量监测', '水质监测', '噪声监测', '振动监测', '温度分布',
    '湿度分布', '压力监测', '流量监测', '液位监测', '气体检测',
    '火灾报警', '入侵报警', '紧急广播', '公共广播', '会议系统',
    '楼宇自控', '智能照明', '窗帘控制', '地暖控制', '中央空调',
    '新风换气', '除湿系统', '加湿系统', '排风系统', '送风系统',
    '冷却塔监控', '水泵监控', '风机监控', '阀门控制', '风阀控制'
  ]

  const descriptions = [
    'HVAC系统监控面板', '电力系统监控面板', '给排水系统监控', '照明系统控制面板',
    '电梯运行状态监控', '消防安全监控中心', '安防系统监控面板', '能源消耗分析面板',
    '环境参数监控面板', '停车场管理面板', '门禁系统控制面板', '视频监控系统面板',
    '新风系统监控面板', '冷站系统监控面板', '热站系统监控面板', '变配电监控面板',
    'UPS电源监控面板', '发电机监控面板', '太阳能监控面板', '风能监控面板',
    '空气质量监测面板', '水质监测面板', '噪声监测面板', '振动监测面板',
    '温度分布监控面板', '湿度分布监控面板', '压力监测面板', '流量监测面板',
    '液位监测面板', '气体检测面板', '火灾报警面板', '入侵报警面板',
    '紧急广播控制面板', '公共广播控制面板', '会议系统控制面板', '楼宇自控面板',
    '智能照明面板', '窗帘控制面板', '地暖控制面板', '中央空调面板',
    '新风换气面板', '除湿系统面板', '加湿系统面板', '排风系统面板',
    '送风系统面板', '冷却塔监控面板', '水泵监控面板', '风机监控面板',
    '阀门控制面板', '风阀控制面板'
  ]

  const panelTypes: PanelType[] = ['Dashboard', 'Graphic']
  const backgroundColors = ['#f0f2f5', '#1a1a2e', '#0f1419', '#2c3e50', '#34495e', '#1e272e', '#2d3436', '#636e72']

  const panels: ScadaPanel[] = []

  for (let i = 0; i < 2; i++) {
    const type = panelTypes[i % 2]
    const bgColor = backgroundColors[i % backgroundColors.length]
    const daysAgo = 50 - i

    panels.push({
      id: `panel-${String(i + 1).padStart(3, '0')}`,
      name: panelNames[i],
      type,
      description: descriptions[i],
      width: 1200 + (i % 5) * 100,
      height: 800 + (i % 4) * 50,
      grid: 20,
      backgroundColor: bgColor,
      components: [
      ],
      createdAt: Date.now() - daysAgo * 86400000,
      updatedAt: Date.now() - (i % 10) * 3600000
    })
  }

  return panels
}

export const useScadaStore = defineStore(
  'scada',
  () => {
  const panels = ref<ScadaPanel[]>(generateSamplePanels())

  const _currentPanelId = ref<string | null>(null)
  const selectedComponentId = ref<string | null>(null)
  const selectedComponentIds = ref<string[]>([])
  const isEditing = ref(true)
  const zoom = ref(1)
  const showGrid = ref(true)
  const isFullscreenPreview = ref(false)

  const currentPanelId = computed({
    get: () => _currentPanelId.value,
    set: (val) => { _currentPanelId.value = val }
  })

  const currentPanel = computed(() => {
    const id = _currentPanelId.value
    if (!id) return null
    return panels.value.find(p => p.id === id) || null
  })

  const selectedComponent = computed(() => {
    if (!currentPanel.value || !selectedComponentId.value) return null
    return currentPanel.value.components.find(c => c.id === selectedComponentId.value) || null
  })

  const createPanel = (name: string, type: PanelType = 'Dashboard', description?: string, width?: number, height?: number) => {
    const panel: ScadaPanel = {
      id: `panel-${Date.now()}`,
      name,
      type,
      description,
      width: width || 1200,
      height: height || 800,
      grid: 20,
      backgroundColor: '#f0f2f5',
      components: [],
      createdAt: Date.now(),
      updatedAt: Date.now()
    }
    panels.value.push(panel)
    return panel
  }

  const deletePanel = (id: string) => {
    const index = panels.value.findIndex(p => p.id === id)
    if (index !== -1) {
      panels.value.splice(index, 1)
      if (_currentPanelId.value === id) {
        _currentPanelId.value = null
      }
    }
  }

  const selectPanel = (id: string) => {
    _currentPanelId.value = id
    selectedComponentId.value = null
  }

  const updatePanel = (updates: Partial<ScadaPanel>) => {
    if (!currentPanel.value) return
    
    Object.assign(currentPanel.value, updates)
    currentPanel.value.updatedAt = Date.now()
  }

  const addComponent = (type: ComponentType, x: number, y: number) => {
    if (!currentPanel.value) return null

    const template = COMPONENT_TEMPLATES.find(t => t.type === type)
    if (!template) return null

    const component: ScadaComponent = {
      id: generateId(),
      type,
      name: template.name,
      x: Math.round(x / currentPanel.value.grid) * currentPanel.value.grid,
      y: Math.round(y / currentPanel.value.grid) * currentPanel.value.grid,
      style: { ...template.defaultStyle },
      binding: null,
      locked: false,
      visible: true,
      ...JSON.parse(JSON.stringify(template.defaultConfig))
    }

    currentPanel.value.components.push(component)
    currentPanel.value.updatedAt = Date.now()
    return component
  }

  const updateComponent = (id: string, updates: Partial<ScadaComponent>) => {
    if (!currentPanel.value) return

    const component = currentPanel.value.components.find(c => c.id === id)
    
    if (component) {
      Object.assign(component, updates)
      currentPanel.value.updatedAt = Date.now()
    }
  }

  const deleteComponent = (id: string) => {
    if (!currentPanel.value) return

    const index = currentPanel.value.components.findIndex(c => c.id === id)
    if (index !== -1) {
      currentPanel.value.components.splice(index, 1)
      currentPanel.value.updatedAt = Date.now()
      if (selectedComponentId.value === id) {
        selectedComponentId.value = null
      }
      selectedComponentIds.value = selectedComponentIds.value.filter(sid => sid !== id)
    }
  }

  const deleteSelectedComponents = () => {
    if (!currentPanel.value || selectedComponentIds.value.length === 0) return
    
    currentPanel.value.components = currentPanel.value.components.filter(
      c => !selectedComponentIds.value.includes(c.id)
    )
    currentPanel.value.updatedAt = Date.now()
    selectedComponentId.value = null
    selectedComponentIds.value = []
  }

  const selectComponent = (id: string | null) => {
    selectedComponentId.value = id
    if (id) {
      selectedComponentIds.value = [id]
    } else {
      selectedComponentIds.value = []
    }
  }

  const selectAllComponents = () => {
    if (!currentPanel.value) return
    selectedComponentIds.value = currentPanel.value.components.map(c => c.id)
    if (selectedComponentIds.value.length > 0) {
      selectedComponentId.value = selectedComponentIds.value[0]
    }
  }

  const clearSelection = () => {
    selectedComponentId.value = null
    selectedComponentIds.value = []
  }

  const moveComponent = (id: string, x: number, y: number) => {
    if (!currentPanel.value) return

    const component = currentPanel.value.components.find(c => c.id === id)
    if (component && !component.locked) {
      component.x = Math.round(x / currentPanel.value.grid) * currentPanel.value.grid
      component.y = Math.round(y / currentPanel.value.grid) * currentPanel.value.grid
      currentPanel.value.updatedAt = Date.now()
    }
  }

  const resizeComponent = (id: string, width: number, height: number) => {
    if (!currentPanel.value) return

    const component = currentPanel.value.components.find(c => c.id === id)
    if (component && !component.locked) {
      component.style.width = Math.round(width / currentPanel.value.grid) * currentPanel.value.grid
      component.style.height = Math.round(height / currentPanel.value.grid) * currentPanel.value.grid
      currentPanel.value.updatedAt = Date.now()
    }
  }

  const bindPoint = (componentId: string, binding: PointBinding | null) => {
    updateComponent(componentId, { binding })
  }

  const duplicateComponent = (id: string) => {
    if (!currentPanel.value) return

    const component = currentPanel.value.components.find(c => c.id === id)
    if (component) {
      const newComponent: ScadaComponent = {
        ...JSON.parse(JSON.stringify(component)),
        id: generateId(),
        x: component.x + 20,
        y: component.y + 20,
        name: `${component.name} (副本)`
      }
      currentPanel.value.components.push(newComponent)
      currentPanel.value.updatedAt = Date.now()
    }
  }

  const clipboard = ref<ScadaComponent[]>([])

  const copyComponent = (id: string) => {
    if (!currentPanel.value) return
    const component = currentPanel.value.components.find(c => c.id === id)
    if (component) {
      clipboard.value = [JSON.parse(JSON.stringify(component))]
    }
  }

  const copySelectedComponents = () => {
    if (!currentPanel.value || selectedComponentIds.value.length === 0) return
    clipboard.value = currentPanel.value.components
      .filter(c => selectedComponentIds.value.includes(c.id))
      .map(c => JSON.parse(JSON.stringify(c)))
  }

  const pasteComponent = (x?: number, y?: number) => {
    if (!currentPanel.value || clipboard.value.length === 0) return
    
    const newIds: string[] = []
    clipboard.value.forEach((clipComp, index) => {
      const newComponent: ScadaComponent = {
        ...clipComp,
        id: generateId(),
        x: x !== undefined ? x + (index * 20) : clipComp.x + 20,
        y: y !== undefined ? y + (index * 20) : clipComp.y + 20,
        name: `${clipComp.name} (副本)`
      }
      currentPanel.value!.components.push(newComponent)
      newIds.push(newComponent.id)
    })
    
    currentPanel.value.updatedAt = Date.now()
    selectedComponentIds.value = newIds
    if (newIds.length > 0) {
      selectedComponentId.value = newIds[0]
    }
  }

  const toggleLock = (id: string) => {
    if (!currentPanel.value) return
    const component = currentPanel.value.components.find(c => c.id === id)
    if (component) {
      component.locked = !component.locked
      currentPanel.value.updatedAt = Date.now()
    }
  }

  const bringToFront = (id: string) => {
    if (!currentPanel.value) return

    const index = currentPanel.value.components.findIndex(c => c.id === id)
    if (index !== -1) {
      const component = currentPanel.value.components.splice(index, 1)[0]
      currentPanel.value.components.push(component)
      currentPanel.value.updatedAt = Date.now()
    }
  }

  const sendToBack = (id: string) => {
    if (!currentPanel.value) return

    const index = currentPanel.value.components.findIndex(c => c.id === id)
    if (index !== -1) {
      const component = currentPanel.value.components.splice(index, 1)[0]
      currentPanel.value.components.unshift(component)
      currentPanel.value.updatedAt = Date.now()
    }
  }

  const scrollToComponentId = ref<string | null>(null)

  const scrollToComponent = (id: string) => {
    scrollToComponentId.value = id
  }

  const clearScrollTarget = () => {
    scrollToComponentId.value = null
  }

  return {
    panels,
    currentPanelId,
    selectedComponentId,
    selectedComponentIds,
    isEditing,
    zoom,
    showGrid,
    isFullscreenPreview,
    currentPanel,
    selectedComponent,
    createPanel,
    deletePanel,
    selectPanel,
    updatePanel,
    addComponent,
    updateComponent,
    deleteComponent,
    deleteSelectedComponents,
    selectComponent,
    selectAllComponents,
    clearSelection,
    moveComponent,
    resizeComponent,
    bindPoint,
    duplicateComponent,
    clipboard,
    copyComponent,
    copySelectedComponents,
    pasteComponent,
    toggleLock,
    bringToFront,
    sendToBack,
    scrollToComponentId,
    scrollToComponent,
    clearScrollTarget
  }
}, {
  persist: {
    key: 'scada-panels',
    paths: ['panels'],
  }
})
