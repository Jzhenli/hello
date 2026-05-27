import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ScadaPanel, ScadaComponent, ComponentType, PointBinding } from '@/types/scada'
import { COMPONENT_TEMPLATES } from '@/types/scada'

function generateId(): string {
  return `comp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export const useScadaStore = defineStore('scada', () => {
  const panels = ref<ScadaPanel[]>([
    {
      id: 'panel-001',
      name: '暖通空调监控',
      description: 'HVAC系统监控面板',
      width: 1200,
      height: 800,
      grid: 20,
      backgroundColor: '#f0f2f5',
      components: [
        {
          id: 'comp-001',
          type: 'gauge',
          name: '温度仪表',
          x: 100,
          y: 100,
          style: { width: 150, height: 150 },
          binding: { deviceId: 'KNX-01', pointName: 'temperature_1', pointDescription: '一楼大厅温度', unit: '°C' },
          gaugeConfig: {
            min: 0,
            max: 50,
            unit: '°C',
            thresholds: [
              { value: 18, color: '#3498db' },
              { value: 26, color: '#27ae60' },
              { value: 50, color: '#e74c3c' }
            ],
            showValue: true
          },
          locked: false,
          visible: true
        },
        {
          id: 'comp-002',
          type: 'gauge',
          name: '湿度仪表',
          x: 300,
          y: 100,
          style: { width: 150, height: 150 },
          binding: { deviceId: 'KNX-01', pointName: 'humidity_1', pointDescription: '一楼大厅湿度', unit: '%' },
          gaugeConfig: {
            min: 0,
            max: 100,
            unit: '%',
            thresholds: [
              { value: 30, color: '#f39c12' },
              { value: 70, color: '#27ae60' },
              { value: 100, color: '#3498db' }
            ],
            showValue: true
          },
          locked: false,
          visible: true
        },
        {
          id: 'comp-003',
          type: 'indicator',
          name: '人体感应',
          x: 500,
          y: 120,
          style: { width: 60, height: 60 },
          binding: { deviceId: 'KNX-01', pointName: 'presence_1', pointDescription: '一楼大厅人体感应' },
          indicatorConfig: {
            onColor: '#27ae60',
            offColor: '#95a5a6',
            blinkOnAlarm: false
          },
          locked: false,
          visible: true
        }
      ],
      createdAt: Date.now() - 86400000,
      updatedAt: Date.now()
    },
    {
      id: 'panel-002',
      name: '电力监控',
      description: '电力系统监控面板',
      width: 1200,
      height: 800,
      grid: 20,
      backgroundColor: '#1a1a2e',
      components: [
        {
          id: 'comp-006',
          type: 'gauge',
          name: '总功率',
          x: 100,
          y: 100,
          style: { width: 180, height: 180 },
          binding: { deviceId: 'MODBUS-01', pointName: 'power_total', pointDescription: '总功率', unit: 'kW' },
          gaugeConfig: {
            min: 0,
            max: 500,
            unit: 'kW',
            thresholds: [
              { value: 200, color: '#27ae60' },
              { value: 400, color: '#f39c12' },
              { value: 500, color: '#e74c3c' }
            ],
            showValue: true
          },
          locked: false,
          visible: true
        }
      ],
      createdAt: Date.now() - 86400000 * 2,
      updatedAt: Date.now() - 3600000
    }
  ])

  const _currentPanelId = ref<string | null>(null)
  const selectedComponentId = ref<string | null>(null)
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

  const createPanel = (name: string, description?: string, width?: number, height?: number) => {
    const panel: ScadaPanel = {
      id: `panel-${Date.now()}`,
      name,
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
    }
  }

  const selectComponent = (id: string | null) => {
    selectedComponentId.value = id
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

  return {
    panels,
    currentPanelId,
    selectedComponentId,
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
    selectComponent,
    moveComponent,
    resizeComponent,
    bindPoint,
    duplicateComponent,
    bringToFront,
    sendToBack
  }
})
