import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { deviceApi } from '@/api/devices'
import { dataApi } from '@/api/data'
import { controlApi } from '@/api/control'
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
  writable: boolean
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

function isPointWritable(point: PointConfig): boolean {
  const config = point.config || {}
  if (config.writable === true) return true
  const registerType = config.register_type as string | undefined
  if (registerType === 'coil' || registerType === 'holding') return true
  const objectType = (config.object_type as string) || point.data_type
  if (objectType && (objectType.includes('Output') || objectType.includes('Value'))) return true
  if (config.control_address) return true
  return false
}

function mapPointToDisplay(point: PointConfig, readingData?: { data: Record<string, unknown>; standardPoints: Map<string, StandardPoint>; timestamp?: number }): PointDisplay {
  const metadata = point.metadata || {}
  const isDigital = point.standard_data_type === 'bool'

  const sp = readingData?.standardPoints?.get(point.name)
  const rawValue = readingData?.data?.[point.name]
  const currentValue = sp?.value ?? (rawValue as number | boolean | string | undefined)
  const timeStr = readingData?.timestamp
    ? new Date(readingData.timestamp * 1000).toLocaleString('zh-CN')
    : undefined

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
    writable: isPointWritable(point),
    currentValue,
    minValue: (metadata.minValue as number) ?? (metadata.range as number[])?.[0],
    maxValue: (metadata.maxValue as number) ?? (metadata.range as number[])?.[1],
    lastUpdate: timeStr,
    quality: (sp?.quality as 'good' | 'bad' | 'uncertain') ?? 'good',
    trend: {
      enabled: (metadata.trendEnabled as boolean) ?? false,
      interval: (metadata.trendInterval as number) ?? 60,
      retention: (metadata.trendRetention as number) ?? 7
    }
  }
}

function mapDeviceWithPoints(device: DeviceConfig, readingData?: { data: Record<string, unknown>; standardPoints: Map<string, StandardPoint>; timestamp?: number }): DeviceWithPoints {
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
    points: (device.points || []).map(p => mapPointToDisplay(p, readingData))
  }
}

function parseStandardPoints(rawSp: any[]): { standardPoints: Map<string, StandardPoint>; timestamp?: number } {
  const standardPoints = new Map<string, StandardPoint>()
  let timestamp: number | undefined
  for (const p of rawSp || []) {
    const key = p.point_name || p.name || ''
    if (key) {
      standardPoints.set(key, {
        name: key,
        point_name: p.point_name,
        value: p.value,
        unit: p.unit,
        data_type: p.data_type,
        quality: p.quality,
        timestamp: p.timestamp
      })
    }
    if (p.timestamp && !timestamp) timestamp = p.timestamp
  }
  return { standardPoints, timestamp }
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
      const [devRes, readRes] = await Promise.allSettled([
        deviceApi.list(),
        deviceApi.getLatest(false)
      ])

      const deviceList = devRes.status === 'fulfilled' ? devRes.value.devices : []
      const readingList = readRes.status === 'fulfilled' ? readRes.value.devices : []

      const readingMap = new Map<string, { data: Record<string, unknown>; standardPoints: Map<string, StandardPoint>; timestamp?: number }>()
      for (const r of readingList) {
        const { standardPoints, timestamp } = parseStandardPoints(r.standard_points)
        readingMap.set(r.asset, { data: r.data || {}, standardPoints, timestamp })
      }

      devices.value = deviceList.map(d => mapDeviceWithPoints(d, readingMap.get(d.asset)))
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
      const [pointsRes, readingRes] = await Promise.allSettled([
        deviceApi.listPoints(asset),
        dataApi.getReadings({ asset, limit: 1, active_only: false })
      ])

      const points = pointsRes.status === 'fulfilled' ? pointsRes.value : []
      const readings = readingRes.status === 'fulfilled' ? readingRes.value.readings : []

      let readingData: { data: Record<string, unknown>; standardPoints: Map<string, StandardPoint>; timestamp?: number } | undefined
      if (readings.length > 0) {
        const r = readings[0]
        const { standardPoints, timestamp } = parseStandardPoints(r.standard_points)
        readingData = { data: r.data || {}, standardPoints, timestamp }
      }

      const deviceIdx = devices.value.findIndex(d => d.asset === asset)
      const mappedPoints = points.map(p => mapPointToDisplay(p, readingData))

      if (deviceIdx !== -1) {
        const device = devices.value[deviceIdx]
        devices.value[deviceIdx] = { ...device, points: mappedPoints, pointCount: mappedPoints.length }
      } else {
        const device = await deviceApi.get(asset)
        const mapped = mapDeviceWithPoints(device, readingData)
        devices.value.push(mapped)
      }
    } catch (e: unknown) {
      console.error(`Failed to fetch points for device ${asset}:`, e)
    }
  }

  async function fetchLatestReadings(_asset: string) {
    // No longer needed - data is merged in fetchDevicePoints/fetchDevicesWithPoints
  }

  async function fetchAllLatestReadings() {
    // No longer needed - data is merged in fetchDevicesWithPoints
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

  function getPointTrendData(pointName: string): { time: string; timestamp: number; value: number; quality: string }[] {
    const data: { time: string; timestamp: number; value: number; quality: string }[] = []

    for (const reading of historyReadings.value) {
      const sp = reading.standard_points?.find(p => (p.name || p.point_name) === pointName)
      const rawVal = reading.data?.[pointName]
      const val = sp?.value ?? rawVal

      if (val !== undefined && val !== null) {
        const date = new Date(reading.timestamp * 1000)
        let numericValue: number
        
        if (typeof val === 'boolean') {
          numericValue = val ? 1 : 0
        } else if (typeof val === 'number') {
          numericValue = val
        } else {
          continue
        }
        
        data.push({
          time: date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
          timestamp: reading.timestamp * 1000,
          value: numericValue,
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

  const generateTrendData = (point: PointDisplay, hours: number = 24) => {
    const now = Date.now()
    const data: { time: string; timestamp: number; value: number; quality: string }[] = []
    const interval = trendAggregation.value === 'none' ? 60000 :
                     trendAggregation.value === '1min' ? 60000 :
                     trendAggregation.value === '5min' ? 300000 :
                     trendAggregation.value === '15min' ? 900000 : 3600000

    const count = (hours * 3600000) / interval
    const isDigital = point.type === 'digital' || point.standard_data_type === 'bool'

    for (let i = count; i >= 0; i--) {
      const timestamp = now - i * interval
      const time = new Date(timestamp)
      const h = time.getHours().toString().padStart(2, '0')
      const m = time.getMinutes().toString().padStart(2, '0')

      let value: number
      if (isDigital) {
        value = Math.random() > 0.5 ? 1 : 0
      } else {
        value = 20 + (Math.random() - 0.5) * 10
      }

      data.push({
        time: `${h}:${m}`,
        timestamp,
        value: isDigital ? value : Math.round(value * 100) / 100,
        quality: Math.random() > 0.05 ? 'good' : 'uncertain'
      })
    }

    return data
  }

  async function writePoint(deviceAsset: string, pointName: string, value: number | boolean | string): Promise<{ success: boolean; message: string }> {
    const device = devices.value.find(d => d.asset === deviceAsset)
    if (!device) {
      return { success: false, message: `设备 ${deviceAsset} 不存在` }
    }

    const point = device.points.find(p => p.name === pointName)
    if (!point) {
      return { success: false, message: `点位 ${pointName} 不存在` }
    }

    if (!point.writable) {
      return { success: false, message: `点位 ${pointName} 不可写` }
    }

    try {
      const res = await controlApi.writeSetpoint(
        device.pluginName,
        deviceAsset,
        pointName,
        value
      )

      if (res.status === 'ACCEPTED') {
        setTimeout(() => fetchDevicePoints(deviceAsset), 2000)
        return { success: true, message: `写值命令已下发 (命令ID: ${res.command_id.slice(0, 8)}...)` }
      }

      return { success: false, message: `命令状态异常: ${res.status}` }
    } catch (e: unknown) {
      const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : '写值失败')
      return { success: false, message: detail }
    }
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
    generateTrendData,
    writePoint
  }
})
