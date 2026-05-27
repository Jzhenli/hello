<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { usePointStore } from '@/stores/points'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, ScatterChart } from 'echarts/charts'
import { 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  MarkLineComponent,
  MarkPointComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  ScatterChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  MarkLineComponent,
  MarkPointComponent
])

const pointStore = usePointStore()

const props = defineProps<{
  deviceName?: string
  pointName?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const timeRangeOptions = [
  { value: '1h', label: '1小时' },
  { value: '6h', label: '6小时' },
  { value: '24h', label: '24小时' },
  { value: '7d', label: '7天' },
  { value: '30d', label: '30天' }
]

const aggregationOptions = [
  { value: 'none', label: '原始数据' },
  { value: '1min', label: '1分钟' },
  { value: '5min', label: '5分钟' },
  { value: '15min', label: '15分钟' },
  { value: '1h', label: '1小时' }
]

const showConfig = ref(false)
const autoRefresh = ref(true)
const refreshInterval = ref(30)
const showMinMax = ref(true)
const showAvgLine = ref(true)
const showDataPoints = ref(false)

let refreshTimer: ReturnType<typeof setInterval> | null = null

const hoursMap: Record<string, number> = {
  '1h': 1,
  '6h': 6,
  '24h': 24,
  '7d': 168,
  '30d': 720
}

const trendData = computed(() => {
  if (!pointStore.selectedPoint || !pointStore.selectedDeviceAsset) return []
  
  const realData = pointStore.getPointTrendData(pointStore.selectedPoint.name)
  if (realData.length > 0) {
    return realData
  }
  
  const hours = hoursMap[pointStore.trendTimeRange] || 24
  return pointStore.generateTrendData(pointStore.selectedPoint, hours)
})

const chartOption = computed(() => {
  if (!pointStore.selectedPoint) return {}
  
  const point = pointStore.selectedPoint
  const data = trendData.value
  const isDigital = point.type === 'digital' || point.standard_data_type === 'bool'
  
  const seriesData = data.map(d => [d.timestamp, d.value])
  
  const statistics = data.length > 0 ? {
    min: Math.min(...data.map(d => d.value)),
    max: Math.max(...data.map(d => d.value)),
    avg: data.reduce((sum, d) => sum + d.value, 0) / data.length
  } : { min: 0, max: 0, avg: 0 }
  
  const markLine: any[] = []
  if (!isDigital) {
    if (showAvgLine.value && data.length > 0) {
      markLine.push({
        name: '平均值',
        yAxis: statistics.avg,
        lineStyle: { color: '#f39c12', type: 'dashed' },
        label: { formatter: `平均: ${statistics.avg.toFixed(2)}` }
      })
    }
    if (showMinMax.value && point.maxValue !== undefined) {
      markLine.push({
        name: '上限',
        yAxis: point.maxValue,
        lineStyle: { color: '#e74c3c', type: 'dashed' },
        label: { formatter: `上限: ${point.maxValue}` }
      })
    }
    if (showMinMax.value && point.minValue !== undefined) {
      markLine.push({
        name: '下限',
        yAxis: point.minValue,
        lineStyle: { color: '#3498db', type: 'dashed' },
        label: { formatter: `下限: ${point.minValue}` }
      })
    }
  }
  
  return {
    title: {
      text: `${point.description || point.name} (${point.name})`,
      left: 'center',
      textStyle: { fontSize: 16, fontWeight: 'normal' }
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = params[0]
        const time = dayjs(d.value[0]).format('MM-DD HH:mm:ss')
        const value = isDigital ? (d.value[1] === 1 ? '开' : '关') : d.value[1]
        return `${time}<br/>值: ${value} ${point.unit || ''}`
      }
    },
    legend: {
      data: isDigital ? ['状态'] : ['数值', '平均值', '上限', '下限'],
      bottom: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true
    },
    toolbox: {
      feature: {
        dataZoom: { yAxisIndex: 'none' },
        restore: {},
        saveAsImage: {}
      }
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        start: 0,
        end: 100
      }
    ],
    xAxis: {
      type: 'time',
      boundaryGap: false,
      axisLabel: {
        formatter: (value: number) => dayjs(value).format('HH:mm')
      }
    },
    yAxis: {
      type: isDigital ? 'category' : 'value',
      name: isDigital ? '' : (point.unit || ''),
      min: isDigital ? undefined : (value: any) => Math.floor(value.min * 0.9),
      max: isDigital ? undefined : (value: any) => Math.ceil(value.max * 1.1),
      data: isDigital ? ['关', '开'] : undefined,
      axisLabel: {
        formatter: isDigital ? (value: string) => value : undefined
      }
    },
    series: [
      {
        name: isDigital ? '状态' : '数值',
        type: 'line',
        smooth: !isDigital,
        step: isDigital ? 'middle' : undefined,
        symbol: showDataPoints.value ? 'circle' : 'none',
        symbolSize: 6,
        sampling: 'lttb',
        itemStyle: { 
          color: isDigital ? (params: any) => params.value[1] === 1 ? '#27ae60' : '#e74c3c' : '#3498db'
        },
        lineStyle: isDigital ? {
          width: 3
        } : undefined,
        areaStyle: isDigital ? {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(39, 174, 96, 0.3)' },
              { offset: 1, color: 'rgba(39, 174, 96, 0.05)' }
            ]
          }
        } : {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(52, 152, 219, 0.3)' },
              { offset: 1, color: 'rgba(52, 152, 219, 0.05)' }
            ]
          }
        },
        data: seriesData,
        markLine: isDigital ? undefined : {
          silent: true,
          data: markLine
        },
        markPoint: !isDigital && showMinMax.value && data.length > 0 ? {
          data: [
            { type: 'max', name: '最大值', itemStyle: { color: '#e74c3c' } },
            { type: 'min', name: '最小值', itemStyle: { color: '#27ae60' } }
          ]
        } : undefined
      }
    ]
  }
})

const statisticsInfo = computed(() => {
  if (!trendData.value.length) return null
  
  const values = trendData.value.map(d => d.value)
  const sum = values.reduce((a, b) => a + b, 0)
  const point = pointStore.selectedPoint
  const isDigital = point?.type === 'digital' || point?.standard_data_type === 'bool'
  
  const onCount = isDigital ? values.filter(v => v === 1).length : 0
  const offCount = isDigital ? values.filter(v => v === 0).length : 0
  
  return {
    min: Math.min(...values).toFixed(2),
    max: Math.max(...values).toFixed(2),
    avg: (sum / values.length).toFixed(2),
    count: values.length,
    start: dayjs(trendData.value[0]?.timestamp).format('MM-DD HH:mm'),
    end: dayjs(trendData.value[trendData.value.length - 1]?.timestamp).format('MM-DD HH:mm'),
    isDigital,
    onCount,
    offCount,
    onPercentage: isDigital ? ((onCount / values.length) * 100).toFixed(1) : undefined
  }
})

const loadData = async () => {
  if (!pointStore.selectedDeviceAsset) return
  const hours = hoursMap[pointStore.trendTimeRange] || 24
  await pointStore.fetchHistoryReadings(pointStore.selectedDeviceAsset, hours)
}

const startAutoRefresh = () => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (autoRefresh.value) {
    refreshTimer = setInterval(() => {
      loadData()
    }, refreshInterval.value * 1000)
  }
}

watch(autoRefresh, () => {
  startAutoRefresh()
})

watch(() => pointStore.trendTimeRange, () => {
  loadData()
})

watch(() => props.deviceName, async (name) => {
  if (name && props.pointName) {
    pointStore.selectPoint(name, props.pointName)
    await loadData()
  }
}, { immediate: true })

onMounted(() => {
  startAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="point-trend">
    <div class="trend-header">
      <div class="header-left">
        <h3>📈 点位趋势</h3>
        <span v-if="pointStore.selectedPoint" class="point-info">
          {{ pointStore.selectedDeviceAsset }} / {{ pointStore.selectedPoint.name }}
        </span>
        <el-tag v-if="pointStore.historyLoading" type="info" size="small">加载中...</el-tag>
      </div>
      <div class="header-right">
        <el-select v-model="pointStore.trendTimeRange" style="width: 100px">
          <el-option
            v-for="opt in timeRangeOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="pointStore.trendAggregation" style="width: 100px">
          <el-option
            v-for="opt in aggregationOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button @click="loadData" :loading="pointStore.historyLoading">刷新</el-button>
        <el-button @click="showConfig = !showConfig">
          ⚙️ 配置
        </el-button>
        <el-button @click="emit('close')">✕ 关闭</el-button>
      </div>
    </div>
    
    <div v-if="showConfig" class="config-panel">
      <div class="config-row">
        <label>自动刷新</label>
        <el-switch v-model="autoRefresh" />
      </div>
      <div class="config-row">
        <label>刷新间隔(秒)</label>
        <el-input-number v-model="refreshInterval" :min="5" :max="300" :disabled="!autoRefresh" />
      </div>
      <div class="config-row">
        <label>显示上下限</label>
        <el-switch v-model="showMinMax" />
      </div>
      <div class="config-row">
        <label>显示平均线</label>
        <el-switch v-model="showAvgLine" />
      </div>
      <div class="config-row">
        <label>显示数据点</label>
        <el-switch v-model="showDataPoints" />
      </div>
    </div>
    
    <div v-if="pointStore.selectedPoint" class="trend-content">
      <div class="chart-container">
        <v-chart :option="chartOption" class="trend-chart" autoresize />
      </div>
      
      <div class="statistics-panel">
        <div class="stat-card">
          <span class="stat-label">当前值</span>
          <span class="stat-value current">
            <template v-if="statisticsInfo?.isDigital">
              {{ pointStore.selectedPoint.currentValue === true || pointStore.selectedPoint.currentValue === 1 ? '开' : '关' }}
            </template>
            <template v-else>
              {{ pointStore.selectedPoint.currentValue ?? '--' }} {{ pointStore.selectedPoint.unit }}
            </template>
          </span>
        </div>
        
        <template v-if="statisticsInfo?.isDigital">
          <div class="stat-card">
            <span class="stat-label">开启次数</span>
            <span class="stat-value on">{{ statisticsInfo?.onCount ?? 0 }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">关闭次数</span>
            <span class="stat-value off">{{ statisticsInfo?.offCount ?? 0 }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">开启率</span>
            <span class="stat-value percentage">{{ statisticsInfo?.onPercentage ?? 0 }}%</span>
          </div>
        </template>
        
        <template v-else>
          <div class="stat-card">
            <span class="stat-label">最小值</span>
            <span class="stat-value min">{{ statisticsInfo?.min ?? '--' }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">最大值</span>
            <span class="stat-value max">{{ statisticsInfo?.max ?? '--' }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">平均值</span>
            <span class="stat-value avg">{{ statisticsInfo?.avg ?? '--' }}</span>
          </div>
        </template>
        
        <div class="stat-card">
          <span class="stat-label">数据点数</span>
          <span class="stat-value">{{ statisticsInfo?.count ?? 0 }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">时间范围</span>
          <span class="stat-value time">{{ statisticsInfo?.start ?? '--' }} ~ {{ statisticsInfo?.end ?? '--' }}</span>
        </div>
      </div>
      
      <div class="point-meta">
        <div class="meta-item">
          <span class="meta-label">点位类型:</span>
          <el-tag size="small">{{ pointStore.selectedPoint.type === 'analog' ? '模拟量' : '数字量' }}</el-tag>
        </div>
        <div class="meta-item">
          <span class="meta-label">数据质量:</span>
          <el-tag :type="pointStore.selectedPoint.quality === 'good' ? 'success' : 'warning'" size="small">
            {{ pointStore.selectedPoint.quality === 'good' ? '良好' : '不确定' }}
          </el-tag>
        </div>
        <div class="meta-item">
          <span class="meta-label">量程:</span>
          <span>{{ pointStore.selectedPoint.minValue ?? '--' }} ~ {{ pointStore.selectedPoint.maxValue ?? '--' }} {{ pointStore.selectedPoint.unit }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">趋势记录:</span>
          <el-tag :type="pointStore.selectedPoint.trend?.enabled ? 'success' : 'info'" size="small">
            {{ pointStore.selectedPoint.trend?.enabled ? '已启用' : '未启用' }}
          </el-tag>
        </div>
      </div>
    </div>
    
    <div v-else class="empty-state">
      <span class="empty-icon">📊</span>
      <p>请从设备列表中选择一个点位查看趋势</p>
    </div>
  </div>
</template>

<style scoped>
.point-trend {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.trend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h3 {
  margin: 0;
  font-size: 16px;
  color: #2c3e50;
}

.point-info {
  font-size: 13px;
  color: #7f8c8d;
  background: #fff;
  padding: 4px 8px;
  border-radius: 4px;
}

.header-right {
  display: flex;
  gap: 8px;
}

.config-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px 16px;
  background: #f0f2f5;
  border-bottom: 1px solid #e0e0e0;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-row label {
  font-size: 13px;
  color: #2c3e50;
  white-space: nowrap;
}

.trend-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
}

.chart-container {
  flex: 1;
  min-height: 300px;
}

.trend-chart {
  width: 100%;
  height: 100%;
}

.statistics-panel {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid #e0e0e0;
  margin-top: 12px;
}

.stat-card {
  flex: 1;
  text-align: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #7f8c8d;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
}

.stat-value.current {
  color: #3498db;
}

.stat-value.min {
  color: #27ae60;
}

.stat-value.max {
  color: #e74c3c;
}

.stat-value.avg {
  color: #f39c12;
}

.stat-value.on {
  color: #27ae60;
}

.stat-value.off {
  color: #e74c3c;
}

.stat-value.percentage {
  color: #9b59b6;
}

.stat-value.time {
  font-size: 12px;
  color: #7f8c8d;
}

.point-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-top: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.meta-label {
  color: #7f8c8d;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #95a5a6;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}
</style>
