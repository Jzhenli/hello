<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDeviceStore } from '@/stores/devices'
import { useRuleStore } from '@/stores/rules'
import { useAlertStore } from '@/stores/alerts'
import { useSystemStore } from '@/stores/system'
import { useResponsive } from '@/utils/useResponsive'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart, GaugeChart } from 'echarts/charts'
import { 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent,
  GridComponent 
} from 'echarts/components'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  PieChart,
  GaugeChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const deviceStore = useDeviceStore()
const ruleStore = useRuleStore()
const alertStore = useAlertStore()
const systemStore = useSystemStore()
const { isTablet, isMobile } = useResponsive()

const currentTime = ref(dayjs().format('YYYY-MM-DD HH:mm:ss'))
let timer: ReturnType<typeof setInterval>

const statCardSpan = computed(() => {
  if (isMobile.value) return 24
  if (isTablet.value) return 12
  return 6
})

const chartColSpan = computed(() => {
  if (isMobile.value) return 24
  if (isTablet.value) return 24
  return { main: 16, side: 8 }
})

const infoColSpan = computed(() => {
  if (isMobile.value) return 24
  if (isTablet.value) return 12
  return 8
})

const dataChartOption = ref({
  tooltip: {
    trigger: 'axis'
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: [] as string[]
  },
  yAxis: {
    type: 'value'
  },
  series: [{
    name: '数据采集量',
    type: 'line',
    smooth: true,
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(52, 152, 219, 0.3)' },
          { offset: 1, color: 'rgba(52, 152, 219, 0.05)' }
        ]
      }
    },
    lineStyle: { color: '#3498db' },
    itemStyle: { color: '#3498db' },
    data: [] as number[]
  }]
})

const deviceChartOption = ref({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)'
  },
  legend: {
    bottom: '5%',
    left: 'center'
  },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    avoidLabelOverlap: false,
    itemStyle: {
      borderRadius: 10,
      borderColor: '#fff',
      borderWidth: 2
    },
    label: {
      show: false
    },
    emphasis: {
      label: {
        show: true,
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    data: [
      { value: deviceStore.onlineDevices, name: '在线', itemStyle: { color: '#27ae60' } },
      { value: deviceStore.totalDevices - deviceStore.onlineDevices, name: '离线', itemStyle: { color: '#e74c3c' } }
    ]
  }]
})

const cpuGaugeOption = ref({
  series: [{
    type: 'gauge',
    startAngle: 200,
    endAngle: -20,
    min: 0,
    max: 100,
    splitNumber: 10,
    itemStyle: {
      color: '#3498db'
    },
    progress: {
      show: true,
      width: 20
    },
    pointer: {
      show: false
    },
    axisLine: {
      lineStyle: {
        width: 20,
        color: [[1, '#e0e0e0']]
      }
    },
    axisTick: {
      show: false
    },
    splitLine: {
      show: false
    },
    axisLabel: {
      show: false
    },
    title: {
      show: false
    },
    detail: {
      valueAnimation: true,
      fontSize: 24,
      fontWeight: 'bold',
      formatter: '{value}%',
      color: '#2c3e50'
    },
    data: [{ value: systemStore.stats.cpuUsage }]
  }]
})

onMounted(async () => {
  await Promise.all([
    deviceStore.fetchDevices(),
    ruleStore.fetchRules(),
  ])
  timer = setInterval(() => {
    currentTime.value = dayjs().format('YYYY-MM-DD HH:mm:ss')
  }, 1000)
  
  const chartData = systemStore.generateChartData()
  dataChartOption.value.xAxis.data = chartData.map(d => d.time)
  dataChartOption.value.series[0].data = chartData.map(d => d.value)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h2>系统总览</h2>
      <span class="update-time">最后更新: {{ currentTime }}</span>
    </div>
    
    <el-row :gutter="isMobile ? 12 : 20" class="stat-cards">
      <el-col :span="statCardSpan">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon devices">
            <span>📱</span>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ deviceStore.onlineDevices }}/{{ deviceStore.totalDevices }}</div>
            <div class="stat-label">在线设备</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="statCardSpan">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon data">
            <span>📊</span>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ systemStore.stats.totalReadings.toLocaleString() }}</div>
            <div class="stat-label">采集总量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="statCardSpan">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon rules">
            <span>📋</span>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ ruleStore.activeRules }}/{{ ruleStore.totalRules }}</div>
            <div class="stat-label">活跃规则</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="statCardSpan">
        <el-card class="stat-card alert" shadow="hover">
          <div class="stat-icon alerts">
            <span>🔔</span>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ alertStore.pendingAlerts }}</div>
            <div class="stat-label">待处理告警</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="isMobile ? 12 : 20" class="chart-row">
      <el-col :span="isTablet || isMobile ? 24 : 16">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>数据采集趋势 (24小时)</span>
            </div>
          </template>
          <v-chart :option="dataChartOption" class="chart" autoresize />
        </el-card>
      </el-col>
      <el-col :span="isTablet || isMobile ? 24 : 8" :class="{ 'mt-20': isTablet || isMobile }">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>设备状态</span>
            </div>
          </template>
          <v-chart :option="deviceChartOption" class="chart" autoresize />
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="isMobile ? 12 : 20" class="info-row">
      <el-col :span="infoColSpan">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <span>系统资源</span>
          </template>
          <div class="resource-grid">
            <div class="resource-item">
              <span class="resource-label">CPU</span>
              <el-progress 
                :percentage="systemStore.stats.cpuUsage" 
                :color="systemStore.stats.cpuUsage > 80 ? '#e74c3c' : '#3498db'"
              />
            </div>
            <div class="resource-item">
              <span class="resource-label">内存</span>
              <el-progress 
                :percentage="systemStore.stats.memoryUsage"
                :color="systemStore.stats.memoryUsage > 80 ? '#e74c3c' : '#27ae60'"
              />
            </div>
            <div class="resource-item">
              <span class="resource-label">磁盘</span>
              <el-progress 
                :percentage="systemStore.stats.diskUsage"
                :color="systemStore.stats.diskUsage > 80 ? '#e74c3c' : '#f39c12'"
              />
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="infoColSpan" :class="{ 'mt-20': isMobile }">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <span>规则执行历史</span>
          </template>
          <div class="execution-list">
            <div 
              v-for="exec in ruleStore.executions.slice(0, 4)" 
              :key="exec.id" 
              class="execution-item"
            >
              <el-icon :class="exec.status === 'success' ? 'success' : 'error'">
                <component :is="exec.status === 'success' ? 'CircleCheck' : 'CircleClose'" />
              </el-icon>
              <span class="exec-name">{{ exec.ruleName }}</span>
              <span class="exec-time">{{ exec.triggeredAt }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="infoColSpan" :class="{ 'mt-20': isTablet || isMobile }">
        <el-card class="info-card alert-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最新告警</span>
              <el-button type="primary" link size="small">全部清除</el-button>
            </div>
          </template>
          <div class="alert-list">
            <div 
              v-for="alert in alertStore.alerts.slice(0, 3)" 
              :key="alert.id" 
              class="alert-item"
              :class="alert.level"
            >
              <span class="alert-icon">
                {{ alert.level === 'critical' ? '🚨' : alert.level === 'warning' ? '⚠️' : '💡' }}
              </span>
              <div class="alert-content">
                <div class="alert-title">{{ alert.ruleName }}</div>
                <div class="alert-desc">{{ alert.message }}</div>
              </div>
              <span class="alert-time">{{ alert.triggeredAt.split(' ')[1] }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 0;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dashboard-header h2 {
  margin: 0;
  font-size: 24px;
  color: #2c3e50;
}

.update-time {
  color: #7f8c8d;
  font-size: 14px;
}

.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  margin-bottom: 12px;
}

.stat-card.alert {
  border-left: 4px solid #e74c3c;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin-right: 16px;
  flex-shrink: 0;
}

.stat-icon.devices {
  background: linear-gradient(135deg, #3498db, #2980b9);
}

.stat-icon.data {
  background: linear-gradient(135deg, #27ae60, #219a52);
}

.stat-icon.rules {
  background: linear-gradient(135deg, #9b59b6, #8e44ad);
}

.stat-icon.alerts {
  background: linear-gradient(135deg, #e74c3c, #c0392b);
}

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #2c3e50;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #7f8c8d;
  margin-top: 4px;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card {
  height: 320px;
}

.chart-card :deep(.el-card__body) {
  height: calc(100% - 60px);
  padding: 10px 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart {
  width: 100%;
  height: 100%;
}

.info-card {
  height: 280px;
}

.info-card :deep(.el-card__body) {
  padding: 15px;
}

.resource-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.resource-label {
  width: 50px;
  font-weight: 500;
  color: #2c3e50;
}

.resource-item :deep(.el-progress) {
  flex: 1;
}

.execution-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.execution-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 6px;
  background: #f8f9fa;
}

.execution-item .success {
  color: #27ae60;
  font-size: 18px;
}

.execution-item .error {
  color: #e74c3c;
  font-size: 18px;
}

.exec-name {
  flex: 1;
  font-size: 13px;
  color: #2c3e50;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exec-time {
  font-size: 12px;
  color: #7f8c8d;
}

.alert-card :deep(.el-card__header) {
  padding: 12px 15px;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  border-radius: 6px;
  background: #f8f9fa;
}

.alert-item.critical {
  background: #fef0f0;
  border-left: 3px solid #e74c3c;
}

.alert-item.warning {
  background: #fdf6ec;
  border-left: 3px solid #e6a23c;
}

.alert-icon {
  font-size: 18px;
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-title {
  font-size: 13px;
  font-weight: 500;
  color: #2c3e50;
}

.alert-desc {
  font-size: 12px;
  color: #7f8c8d;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-time {
  font-size: 11px;
  color: #95a5a6;
}

.mt-20 {
  margin-top: 20px;
}

@media (max-width: 1024px) {
  .dashboard-header h2 {
    font-size: 20px;
  }
  
  .stat-card {
    padding: 16px;
  }
  
  .stat-icon {
    width: 50px;
    height: 50px;
    font-size: 24px;
  }
  
  .stat-value {
    font-size: 24px;
  }
  
  .chart-card {
    height: 280px;
  }
  
  .info-card {
    height: auto;
    min-height: 240px;
  }
}

@media (max-width: 768px) {
  .dashboard-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .dashboard-header h2 {
    font-size: 18px;
  }
  
  .update-time {
    font-size: 12px;
  }
  
  .stat-card {
    padding: 12px;
  }
  
  .stat-icon {
    width: 48px;
    height: 48px;
    font-size: 22px;
    margin-right: 12px;
  }
  
  .stat-value {
    font-size: 22px;
  }
  
  .stat-label {
    font-size: 12px;
  }
  
  .chart-card {
    height: 240px;
    margin-bottom: 12px;
  }
  
  .info-card {
    min-height: 200px;
    margin-bottom: 12px;
  }
}
</style>
