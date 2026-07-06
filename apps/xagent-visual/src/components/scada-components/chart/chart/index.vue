<template>
  <div class="chart-container">
    <div v-if="binding" class="chart-title">
      {{ binding.pointDescription || binding.pointName }}
    </div>
    <v-chart :option="chartOption" class="chart" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onUnmounted } from 'vue'
import type { ScadaComponent } from '@/types/scada'
import { useComponentBinding } from '@/composables/useComponentBinding'
import { usePointStore } from '@/stores/points'
import { useScadaStore } from '@/stores/scada'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent])

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const pointStore = usePointStore()
const scadaStore = useScadaStore()
const chartConfig = computed(() => props.config.chartConfig)
const binding = computed(() => props.config.binding)

const { boundPoint } = useComponentBinding(binding, {
  autoRefresh: true,
  refreshInterval: 10000
})

let refreshTimer: ReturnType<typeof setInterval> | null = null

const hoursMap: Record<string, number> = {
  '1h': 1,
  '6h': 6,
  '24h': 24,
  '7d': 168
}

// 加载历史数据
const loadHistoryData = async () => {
  if (scadaStore.isEditing || !binding.value) return
  
  const deviceId = binding.value.deviceId
  const hours = hoursMap[chartConfig.value?.timeRange || '24h'] || 24
  
  await pointStore.fetchHistoryReadings(deviceId, hours)
}

// 启动自动刷新
const startAutoRefresh = () => {
  if (scadaStore.isEditing) return
  if (refreshTimer) clearInterval(refreshTimer)
  
  refreshTimer = setInterval(() => {
    loadHistoryData()
  }, 30000) // 30秒刷新一次
}

// 停止自动刷新
const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// 监听编辑模式变化
watch(() => scadaStore.isEditing, (isEditing) => {
  if (isEditing) {
    stopAutoRefresh()
  } else {
    loadHistoryData()
    startAutoRefresh()
  }
})

// 监听时间范围变化
watch(() => chartConfig.value?.timeRange, () => {
  if (!scadaStore.isEditing) {
    loadHistoryData()
  }
})

onMounted(() => {
  if (!scadaStore.isEditing && binding.value) {
    loadHistoryData()
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})

const chartOption = computed(() => {
  const isLine = props.config.type === 'chart-line'
  
  let data: number[] = []
  if (boundPoint.value) {
    if (scadaStore.isEditing) {
      // 编辑模式：使用随机数据作为预览
      const hours = hoursMap[chartConfig.value?.timeRange || '24h'] || 24
      const trendData = pointStore.generateTrendData(boundPoint.value, hours)
      data = trendData.map(d => d.value)
    } else {
      // 预览模式：使用真实历史数据
      const realData = pointStore.getPointTrendData(boundPoint.value.name)
      if (realData.length > 0) {
        data = realData.map(d => d.value)
      } else {
        // 如果没有历史数据，fallback 到随机数据
        const hours = hoursMap[chartConfig.value?.timeRange || '24h'] || 24
        const trendData = pointStore.generateTrendData(boundPoint.value, hours)
        data = trendData.map(d => d.value)
      }
    }
  }
  
  return {
    grid: {
      left: '10%',
      right: '5%',
      top: '10%',
      bottom: '15%'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      show: false,
      data: data.map((_, i) => i)
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: { color: 'var(--border-light)' }
      },
      axisLabel: {
        fontSize: 10
      }
    },
    series: [{
      type: isLine ? 'line' : 'bar',
      data: data,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: chartConfig.value?.lineColor || 'var(--color-primary)',
        width: 2
      },
      areaStyle: chartConfig.value?.areaFill ? {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${chartConfig.value?.lineColor || '#3498db'}40` },
            { offset: 1, color: `${chartConfig.value?.lineColor || '#3498db'}05` }
          ]
        }
      } : undefined,
      itemStyle: {
        color: chartConfig.value?.lineColor || 'var(--color-primary)'
      }
    }]
  }
})
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-container);
  border-radius: 8px;
  overflow: hidden;
}

.chart-title {
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-light);
}

.chart {
  flex: 1;
  min-height: 0;
}
</style>
