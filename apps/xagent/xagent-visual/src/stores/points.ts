import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { deviceApi } from '@/api/devices'
import { dataApi } from '@/api/data'
import type { Reading, StandardPoint } from '@/api/data'
import type { DeviceConfig, PointConfig } from '@/api/types'

export interface PointDisplay {
  name: string
  description: string
  data_type: string
  standard_data_type?: string
  unit: string
  enabled: boolean
  config: Record<string, unknown>
  metadata: Record<string, unknown>
  tags: string[]
  type?: 'analog' | 'digital'
  currentValue?: number | boolean | string
  minValue?: number
  maxValue?: number
  lastUpdate?: string
  quality?: 'good' | 'bad' | 'uncertain'
  trend?: {
    enabled: boolean
    interval: number
    retention: number
  }
}

export interface DeviceWithPoints {
  asset: string
  name: string
  enabled: boolean
  status: string
  pluginName: string
  pointCount: number
  connection: {
    host: string
    port: number
  }
  points: PointDisplay[]
}

function mapPointToDisplay(point: PointConfig): PointDisplay {
  const metadata = point.metadata || {}
  const isDigital = point.standard_data_type === 'bool'
  return {
    name: point.name,
    description: point.description || '',
    data_type: point.data_type,
    standard_data_type: point.standard_data_type,
    unit: point.unit || '',
    enabled: point.enabled,
    config: point.config || {},
    metadata: point.metadata || {},
    tags: point.tags || [],
    type: isDigital ? 'digital' : 'analog',
    minValue: (metadata.minValue as number) ?? (metadata.range as number[])?.[0],
    maxValue: (metadata.maxValue as number) ?? (metadata.range as number[])?.[1],
    quality: 'good',
    trend: {
      enabled: (metadata.trendEnabled as boolean) ?? false,
      interval: (metadata.trendInterval as number) ?? 60,
      retention: (metadata.trendRetention as number) ?? 7
    }
  }
}

function mapDeviceWithPoints(device: DeviceConfig): DeviceWithPoints {
  const pluginConfig = device.plugin?.config || {}
  return {
    asset: device.asset,
    name: device.name || device.asset,
    enabled: device.enabled,
    status: device.status || 'active',
    pluginName: device.plugin?.name || '',
    pointCount: device.points?.length || 0,
    connection: {
      host: (pluginConfig.host as string) || '',
      port: (pluginConfig.port as number) || 0
    },
    points: (device.points || []).map(mapPointToDisplay)
  }
}

export const usePointStore = defineStore('points', () => {
  const devices = ref<DeviceWithPoints[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedPoint = ref<PointDisplay | null>(null)
  const selectedDeviceAsset = ref<string | null>(null)
  const trendTimeRange = ref<'1h' | '6h' | '24h' | '7d' | '30d'>('24h')
  const trendAggregation = ref<'none' | '1min' | '5min' | '15min' | '1h'>('5min')

  const latestReadings = ref<Map<string, Reading>>(new Map())
  const historyReadings = ref<Reading[]>([])
  const historyLoading = ref(false)

  const allPoints = computed(() => {
    const points: (PointDisplay & { deviceAsset: string; deviceName: string })[] = []
    devices.value.forEach(device => {
      device.points.forEach(point => {
        points.push({ ...point, deviceAsset: device.asset, deviceName: device.name })
      })
    })
    return points
  })

  async function fetchDevicesWithPoints() {
    loading.value = true
    error.value = null
    try {
      const res = await deviceApi.list()
      devices.value = res.devices.map(mapDeviceWithPoints)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '获取设备点位失败'
      error.value = msg
      console.error('Failed to fetch devices with points:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchDevicePoints(asset: string) {
    try {
      const points = await deviceApi.listPoints(asset)
      const deviceIdx = devices.value.findIndex(d => d.asset === asset)
      if (deviceIdx !== -1) {
        devices.value[deviceIdx].points = points.map(mapPointToDisplay)
        devices.value[deviceIdx].pointCount = points.length
      } else {
        const device = await deviceApi.get(asset)
        const mapped = mapDeviceWithPoints(device)
        devices.value.push(mapped)
      }
    } catch (e: unknown) {
      console.error(`Failed to fetch points for device ${asset}:`, e)
    }
  }

  async function fetchLatestReadings(asset: string) {
    try {
      const res = await dataApi.getReadings({ asset, limit: 1, active_only: false })
      if (res.readings.length > 0) {
        const reading = res.readings[0]
        latestReadings.value.set(asset, reading)
        _applyReadingToPoints(asset, reading)
      }
    } catch (e: unknown) {
      console.error(`Failed to fetch latest readings for ${asset}:`, e)
    }
  }

  async function fetchAllLatestReadings() {
    try {
      const res = await deviceApi.getLatest(false)
      if (res.devices && res.devices.length > 0) {
        for (const readingData of res.devices) {
          const reading: Reading = {
            asset: readingData.asset,
            timestamp: readingData.timestamp,
            service_name: readingData.service_name || '',
            data: readingData.data || {},
            tags: readingData.tags || [],
            standard_points: readingData.standard_points || [],
            device_status: readingData.device_status || null
          }
          latestReadings.value.set(reading.asset, reading)
          _applyReadingToPoints(reading.asset, reading)
        }
      }
    } catch (e: unknown) {
      console.error('Failed to fetch all latest readings:', e)
    }
  }

  async function fetchHistoryReadings(asset: string, hours: number = 24) {
    historyLoading.value = true
    try {
      const endTime = Date.now() / 1000
      const startTime = endTime - hours * 3600
      const res = await dataApi.getHistoryReadings(asset, startTime, endTime, 1000)
      historyReadings.value = res.readings
      return res.readings
    } catch (e: unknown) {
      console.error(`Failed to fetch history for ${asset}:`, e)
      return []
    } finally {
      historyLoading.value = false
    }
  }

  function _applyReadingToPoints(asset: string, reading: Reading) {
    const deviceIdx = devices.value.findIndex(d => d.asset === asset)
    if (deviceIdx === -1) return

    const device = devices.value[deviceIdx]
    const data = reading.data || {}
    const standardPoints = reading.standard_points || []
    const spMap = new Map<string, StandardPoint>()
    for (const sp of standardPoints) {
      spMap.set(sp.name, sp)
    }

    const updatedPoints = device.points.map(point => {
      const sp = spMap.get(point.name)
      const rawValue = data[point.name]
      const timeStr = reading.timestamp
        ? new Date(reading.timestamp * 1000).toLocaleString('zh-CN')
        : undefined

      return {
        ...point,
        currentValue: sp?.value ?? (rawValue as number | boolean | string | undefined) ?? point.currentValue,
        lastUpdate: timeStr || point.lastUpdate,
        quality: (sp?.quality as 'good' | 'bad' | 'uncertain') ?? point.quality
      }
    })

    devices.value[deviceIdx] = { ...device, points: updatedPoints }
  }

  function getPointTrendData(pointName: string): { time: string; timestamp: number; value: number; quality: string }[] {
    const data: { time: string; timestamp: number; value: number; quality: string }[] = []

    for (const reading of historyReadings.value) {
      const sp = reading.standard_points?.find(p => p.name === pointName)
      const rawVal = reading.data?.[pointName]
      const val = sp?.value ?? rawVal

      if (val !== undefined && val !== null && typeof val === 'number') {
        const date = new Date(reading.timestamp * 1000)
        data.push({
          time: date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
          timestamp: reading.timestamp * 1000,
          value: val,
          quality: sp?.quality || 'good'
        })
      }
    }

    return data.sort((a, b) => a.timestamp - b.timestamp)
  }

  async function addPoint(asset: string, point: PointConfig) {
    const res = await deviceApi.addPoint(asset, point)
    if (res.success) {
      await fetchDevicePoints(asset)
    }
    return res
  }

  async function updatePoint(asset: string, pointName: string, updates: Record<string, unknown>) {
    const res = await deviceApi.updatePoint(asset, pointName, updates)
    if (res.success) {
      await fetchDevicePoints(asset)
    }
    return res
  }

  async function removePoint(asset: string, pointName: string) {
    await deviceApi.removePoint(asset, pointName)
    await fetchDevicePoints(asset)
  }

  function selectPoint(deviceAsset: string, pointName: string) {
    const device = devices.value.find(d => d.asset === deviceAsset)
    if (device) {
      const point = device.points.find(p => p.name === pointName)
      if (point) {
        selectedPoint.value = point
        selectedDeviceAsset.value = deviceAsset
      }
    }
  }

  function clearSelection() {
    selectedPoint.value = null
    selectedDeviceAsset.value = null
  }

  function getDevicePoints(deviceAsset: string): PointDisplay[] {
    const device = devices.value.find(d => d.asset === deviceAsset)
    return device?.points || []
  }

  const generateTrendData = (_point: PointDisplay, hours: number = 24) => {
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
      const h = time.getHours().toString().padStart(2, '0')
      const m = time.getMinutes().toString().padStart(2, '0')

      const value = 20 + (Math.random() - 0.5) * 10

      data.push({
        time: `${h}:${m}`,
        timestamp,
        value: Math.round(value * 100) / 100,
        quality: Math.random() > 0.05 ? 'good' : 'uncertain'
      })
    }

    return data
  }

  return {
    devices,
    loading,
    error,
    selectedPoint,
    selectedDeviceAsset,
    trendTimeRange,
    trendAggregation,
    latestReadings,
    historyReadings,
    historyLoading,
    allPoints,
    fetchDevicesWithPoints,
    fetchDevicePoints,
    fetchLatestReadings,
    fetchAllLatestReadings,
    fetchHistoryReadings,
    getPointTrendData,
    addPoint,
    updatePoint,
    removePoint,
    selectPoint,
    clearSelection,
    getDevicePoints,
    generateTrendData
  }
})
