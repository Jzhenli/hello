import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Point {
  name: string
  description: string
  type: 'analog' | 'digital'
  unit: string
  currentValue: number | boolean
  minValue: number
  maxValue: number
  lastUpdate: string
  quality: 'good' | 'bad' | 'uncertain'
  trend: {
    enabled: boolean
    interval: number
    retention: number
  }
}

export interface DeviceWithPoints {
  name: string
  enabled: boolean
  assetName: string
  protocol: string
  status: 'online' | 'offline'
  pointCount: number
  lastUpdate: string
  connection: {
    host: string
    port: number
  }
  points: Point[]
}

export const usePointStore = defineStore('points', () => {
  const devices = ref<DeviceWithPoints[]>([
    {
      name: 'KNX-01',
      enabled: true,
      assetName: 'knx_building',
      protocol: 'KNX',
      status: 'online',
      pointCount: 128,
      lastUpdate: '2分钟前',
      connection: { host: '192.168.1.100', port: 3671 },
      points: [
        {
          name: 'temperature_1',
          description: '一楼大厅温度',
          type: 'analog',
          unit: '°C',
          currentValue: 24.5,
          minValue: 0,
          maxValue: 50,
          lastUpdate: '10秒前',
          quality: 'good',
          trend: { enabled: true, interval: 60, retention: 7 }
        },
        {
          name: 'humidity_1',
          description: '一楼大厅湿度',
          type: 'analog',
          unit: '%',
          currentValue: 65,
          minValue: 0,
          maxValue: 100,
          lastUpdate: '10秒前',
          quality: 'good',
          trend: { enabled: true, interval: 60, retention: 7 }
        },
        {
          name: 'light_1',
          description: '一楼大厅照度',
          type: 'analog',
          unit: 'lux',
          currentValue: 450,
          minValue: 0,
          maxValue: 2000,
          lastUpdate: '15秒前',
          quality: 'good',
          trend: { enabled: true, interval: 60, retention: 7 }
        },
        {
          name: 'presence_1',
          description: '一楼大厅人体感应',
          type: 'digital',
          unit: '',
          currentValue: true,
          minValue: 0,
          maxValue: 1,
          lastUpdate: '5秒前',
          quality: 'good',
          trend: { enabled: false, interval: 60, retention: 7 }
        },
        {
          name: 'co2_1',
          description: '一楼大厅CO2浓度',
          type: 'analog',
          unit: 'ppm',
          currentValue: 650,
          minValue: 0,
          maxValue: 5000,
          lastUpdate: '30秒前',
          quality: 'good',
          trend: { enabled: true, interval: 60, retention: 7 }
        }
      ]
    },
    {
      name: 'MODBUS-01',
      enabled: true,
      assetName: 'modbus_plant',
      protocol: 'Modbus TCP',
      status: 'online',
      pointCount: 64,
      lastUpdate: '1分钟前',
      connection: { host: '192.168.1.101', port: 502 },
      points: [
        {
          name: 'power_total',
          description: '总功率',
          type: 'analog',
          unit: 'kW',
          currentValue: 156.8,
          minValue: 0,
          maxValue: 500,
          lastUpdate: '20秒前',
          quality: 'good',
          trend: { enabled: true, interval: 30, retention: 30 }
        },
        {
          name: 'voltage_l1',
          description: 'L1相电压',
          type: 'analog',
          unit: 'V',
          currentValue: 220.5,
          minValue: 0,
          maxValue: 300,
          lastUpdate: '20秒前',
          quality: 'good',
          trend: { enabled: true, interval: 30, retention: 30 }
        },
        {
          name: 'current_l1',
          description: 'L1相电流',
          type: 'analog',
          unit: 'A',
          currentValue: 45.2,
          minValue: 0,
          maxValue: 100,
          lastUpdate: '20秒前',
          quality: 'good',
          trend: { enabled: true, interval: 30, retention: 30 }
        }
      ]
    },
    {
      name: 'BACNET-01',
      enabled: false,
      assetName: 'bacnet_hvac',
      protocol: 'BACnet',
      status: 'offline',
      pointCount: 32,
      lastUpdate: '连接失败',
      connection: { host: '192.168.1.102', port: 47808 },
      points: []
    }
  ])

  const selectedPoint = ref<Point | null>(null)
  const selectedDevice = ref<string | null>(null)
  const trendTimeRange = ref<'1h' | '6h' | '24h' | '7d' | '30d'>('24h')
  const trendAggregation = ref<'none' | '1min' | '5min' | '15min' | '1h'>('5min')

  const allPoints = computed(() => {
    const points: (Point & { deviceName: string })[] = []
    devices.value.forEach(device => {
      device.points.forEach(point => {
        points.push({ ...point, deviceName: device.name })
      })
    })
    return points
  })

  const generateTrendData = (point: Point, hours: number = 24) => {
    const now = Date.now()
    const data: { time: string; timestamp: number; value: number; quality: string }[] = []
    const interval = trendAggregation.value === 'none' ? 60000 : 
                     trendAggregation.value === '1min' ? 60000 :
                     trendAggregation.value === '5min' ? 300000 :
                     trendAggregation.value === '15min' ? 900000 : 3600000
    
    const count = (hours * 3600000) / interval
    
    for (let i = count; i >= 0; i--) {
      const timestamp = now - i * interval
      const time = new Date(timestamp)
      const hours = time.getHours().toString().padStart(2, '0')
      const minutes = time.getMinutes().toString().padStart(2, '0')
      
      let value: number
      if (point.type === 'digital') {
        value = Math.random() > 0.5 ? 1 : 0
      } else {
        const base = typeof point.currentValue === 'number' ? point.currentValue : 25
        const variance = (point.maxValue - point.minValue) * 0.1
        value = base + (Math.random() - 0.5) * variance
      }
      
      data.push({
        time: `${hours}:${minutes}`,
        timestamp,
        value: Math.round(value * 100) / 100,
        quality: Math.random() > 0.05 ? 'good' : 'uncertain'
      })
    }
    
    return data
  }

  const selectPoint = (deviceName: string, pointName: string) => {
    const device = devices.value.find(d => d.name === deviceName)
    if (device) {
      const point = device.points.find(p => p.name === pointName)
      if (point) {
        selectedPoint.value = point
        selectedDevice.value = deviceName
      }
    }
  }

  const clearSelection = () => {
    selectedPoint.value = null
    selectedDevice.value = null
  }

  return {
    devices,
    selectedPoint,
    selectedDevice,
    trendTimeRange,
    trendAggregation,
    allPoints,
    generateTrendData,
    selectPoint,
    clearSelection
  }
})
