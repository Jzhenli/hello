import { defineStore } from 'pinia'
import { ref } from 'vue'
import { systemApi } from '@/api/system'
import { dataApi } from '@/api/data'

export interface SystemStats {
  cpuUsage: number
  memoryUsage: number
  diskUsage: number
  uptime: number
  totalReadings: number
  todayReadings: number
  connectionCount: number
  processCount: number
  loadAverage: number[]
}

export interface DataQualityStats {
  good: number
  bad: number
  uncertain: number
  total: number
  qualityRate: number
}

export const useSystemStore = defineStore('system', () => {
  const stats = ref<SystemStats>({
    cpuUsage: 0,
    memoryUsage: 0,
    diskUsage: 0,
    uptime: 0,
    totalReadings: 0,
    todayReadings: 0,
    connectionCount: 0,
    processCount: 0,
    loadAverage: [0, 0, 0]
  })

  const dataQuality = ref<DataQualityStats>({
    good: 0,
    bad: 0,
    uncertain: 0,
    total: 0,
    qualityRate: 0
  })

  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSystemStats() {
    try {
      const res = await systemApi.getSystemStats()
      stats.value = {
        cpuUsage: res.cpu_usage,
        memoryUsage: res.memory_usage,
        diskUsage: res.disk_usage,
        uptime: res.uptime,
        totalReadings: res.total_readings,
        todayReadings: res.today_readings,
        connectionCount: res.connection_count,
        processCount: res.process_count,
        loadAverage: res.load_average
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '获取系统统计失败'
      error.value = msg
      console.error('Failed to fetch system stats:', e)
    }
  }

  async function fetchDataQuality() {
    try {
      const res = await dataApi.getDataQuality()
      dataQuality.value = {
        good: res.good,
        bad: res.bad,
        uncertain: res.uncertain,
        total: res.total,
        qualityRate: res.quality_rate
      }
    } catch (e: unknown) {
      console.error('Failed to fetch data quality:', e)
    }
  }

  async function fetchAllStats() {
    loading.value = true
    error.value = null
    try {
      await Promise.all([
        fetchSystemStats(),
        fetchDataQuality()
      ])
    } finally {
      loading.value = false
    }
  }

  const generateChartData = async (timeRange: string = '24h') => {
    try {
      const now = Date.now()
      let startTime: number
      let interval: 'hour' | 'day'
      
      // 根据时间范围计算起始时间和统计间隔
      switch (timeRange) {
        case '1h':
          startTime = now - 1 * 3600000  // 1小时前
          interval = 'hour'
          break
        case '24h':
          startTime = now - 24 * 3600000  // 24小时前
          interval = 'hour'
          break
        case '7d':
          startTime = now - 7 * 24 * 3600000  // 7天前
          interval = 'day'
          break
        default:
          startTime = now - 24 * 3600000  // 默认24小时
          interval = 'hour'
      }
      
      const res = await dataApi.getCollectionStats({
        start_time: startTime / 1000, // 转换为秒
        end_time: now / 1000,
        interval: interval
      })
      
      // 直接使用后端返回的时间字符串（本地时间）
      return res.stats.map(item => ({
        time: item.time,
        value: item.count
      }))
    } catch (e: unknown) {
      console.error('Failed to fetch collection stats:', e)
      // 抛出错误让调用方处理
      throw new Error('获取数据采集统计失败,请稍后重试')
    }
  }

  const generateTemperatureData = () => {
    const now = Date.now()
    const data: { time: string; temp: number; humidity: number }[] = []
    
    for (let i = 24; i >= 0; i--) {
      const time = new Date(now - i * 3600000)
      const hour = time.getHours().toString().padStart(2, '0')
      data.push({
        time: `${hour}:00`,
        temp: Math.floor(Math.random() * 10) + 20,
        humidity: Math.floor(Math.random() * 30) + 40
      })
    }
    
    return data
  }

  return {
    stats,
    dataQuality,
    loading,
    error,
    fetchSystemStats,
    fetchDataQuality,
    fetchAllStats,
    generateChartData,
    generateTemperatureData
  }
}, {
  persist: {
    key: 'xagent-system-v1',
    storage: sessionStorage,
    // 系统统计数据时效性较短，可选择不持久化
    // 但为了优化页面切换体验，保留持久化
    paths: ['stats', 'dataQuality']
  }
})
