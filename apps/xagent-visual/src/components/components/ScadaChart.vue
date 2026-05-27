<script setup lang="ts">
import { computed } from 'vue'
import type { ScadaComponent } from '@/types/scada'
import { usePointStore } from '@/stores/points'
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

const chartConfig = computed(() => props.config.chartConfig)
const binding = computed(() => props.config.binding)

const chartOption = computed(() => {
  const isLine = props.config.type === 'chart-line'
  
  let data: number[] = []
  if (binding.value) {
    const device = pointStore.devices.find(d => d.asset === binding.value!.deviceId || d.name === binding.value!.deviceId)
    const point = device?.points.find(p => p.name === binding.value!.pointName)
    if (point) {
      const hours = chartConfig.value?.timeRange === '1h' ? 1 : 
                    chartConfig.value?.timeRange === '6h' ? 6 :
                    chartConfig.value?.timeRange === '7d' ? 168 : 24
      const trendData = pointStore.generateTrendData(point, hours)
      data = trendData.map(d => d.value)
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
        lineStyle: { color: '#eee' }
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
        color: chartConfig.value?.lineColor || '#3498db',
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
        color: chartConfig.value?.lineColor || '#3498db'
      }
    }]
  }
})
</script>

<template>
  <div class="chart-container">
    <div v-if="binding" class="chart-title">
      {{ binding.pointDescription || binding.pointName }}
    </div>
    <v-chart :option="chartOption" class="chart" autoresize />
  </div>
</template>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.chart-title {
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  color: #2c3e50;
  border-bottom: 1px solid #eee;
}

.chart {
  flex: 1;
  min-height: 0;
}
</style>
