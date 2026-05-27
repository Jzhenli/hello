import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface SystemStats {
  cpuUsage: number
  memoryUsage: number
  diskUsage: number
  uptime: number
  totalReadings: number
  todayReadings: number
}

export const useSystemStore = defineStore('system', () => {
  const stats = ref<SystemStats>({
    cpuUsage: 45,
    memoryUsage: 62,
    diskUsage: 38,
    uptime: 864000,
    totalReadings: 125456,
    todayReadings: 3456
  })

  const generateChartData = (hours: number = 24) => {
    const now = Date.now()
    const data: { time: string; value: number }[] = []
    
    for (let i = hours; i >= 0; i--) {
      const time = new Date(now - i * 3600000)
      const hour = time.getHours().toString().padStart(2, '0')
      data.push({
        time: `${hour}:00`,
        value: Math.floor(Math.random() * 500) + 100
      })
    }
    
    return data
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
    generateChartData,
    generateTemperatureData
  }
})
