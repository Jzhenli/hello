import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { deviceApi } from '@/api/devices'
import type { DeviceConfig, DeviceStatus, BatchOperationResult } from '@/api/types'

export interface DeviceListItem {
  asset: string
  name: string
  enabled: boolean
  status: DeviceStatus
  connectionStatus: 'online' | 'offline' | 'unknown'
  pluginName: string
  pointCount: number
  connection: {
    host: string
    port: number
  }
  pluginConfig: Record<string, unknown>
  tags: string[]
  created_at?: string
  updated_at?: string
}

function mapDeviceToListItem(device: DeviceConfig, connectionStatusMap: Record<string, string> = {}): DeviceListItem {
  const pluginConfig = device.plugin?.config || {}
  const pluginName = device.plugin?.name || ''
  
  let host = ''
  let port = 0
  
  if (pluginName === 'knx') {
    host = (pluginConfig.gateway_ip as string) || ''
    port = (pluginConfig.gateway_port as number) || 0
  } else {
    host = (pluginConfig.host as string) || ''
    port = (pluginConfig.port as number) || 0
  }
  
  const connectionStatus = connectionStatusMap[device.asset] || 'unknown'
  
  return {
    asset: device.asset,
    name: device.name || device.asset,
    enabled: device.enabled,
    status: device.status || 'active',
    connectionStatus: connectionStatus as 'online' | 'offline' | 'unknown',
    pluginName: pluginName,
    pointCount: device.points?.length || 0,
    connection: {
      host: host,
      port: port
    },
    pluginConfig: pluginConfig as Record<string, unknown>,
    tags: device.tags || [],
    created_at: device.created_at,
    updated_at: device.updated_at
  }
}

export const useDeviceStore = defineStore('devices', () => {
  const devices = ref<DeviceConfig[]>([])
  const connectionStatusMap = ref<Record<string, string>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  const deviceList = computed<DeviceListItem[]>(() =>
    devices.value.map(d => mapDeviceToListItem(d, connectionStatusMap.value))
  )

  const onlineDevices = computed(() =>
    deviceList.value.filter(d => d.connectionStatus === 'online').length
  )

  const totalDevices = computed(() => devices.value.length)

  const totalPoints = computed(() =>
    devices.value.reduce((sum, d) => sum + (d.points?.length || 0), 0)
  )

  const southDevices = computed(() =>
    deviceList.value
  )

  async function fetchDevices() {
    loading.value = true
    error.value = null
    try {
      const res = await deviceApi.list()
      devices.value = res.devices
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '获取设备列表失败'
      error.value = msg
      console.error('Failed to fetch devices:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchConnectionStatus() {
    try {
      connectionStatusMap.value = await deviceApi.getConnectionStatus()
    } catch (e: unknown) {
      console.error('Failed to fetch connection status:', e)
    }
  }

  async function createDevice(device: DeviceConfig) {
    const res = await deviceApi.create(device)
    if (res.success) {
      await fetchDevices()
    }
    return res
  }

  async function updateDevice(asset: string, updates: Record<string, unknown>) {
    const res = await deviceApi.update(asset, updates)
    if (res.success) {
      await fetchDevices()
    }
    return res
  }

  async function deleteDevice(asset: string) {
    await deviceApi.delete(asset)
    await fetchDevices()
  }

  async function toggleDevice(asset: string) {
    const device = devices.value.find(d => d.asset === asset)
    if (device) {
      await deviceApi.update(asset, { enabled: !device.enabled })
      await fetchDevices()
    }
  }

  async function reloadDevice(asset: string) {
    return await deviceApi.reload(asset)
  }

  async function batchCreate(devices: DeviceConfig[]): Promise<BatchOperationResult> {
    const result = await deviceApi.batchCreate(devices)
    await fetchDevices()
    return result
  }

  function getDeviceByAsset(asset: string): DeviceConfig | undefined {
    return devices.value.find(d => d.asset === asset)
  }

  return {
    devices,
    deviceList,
    southDevices,
    loading,
    error,
    onlineDevices,
    totalDevices,
    totalPoints,
    connectionStatusMap,
    fetchDevices,
    fetchConnectionStatus,
    createDevice,
    updateDevice,
    deleteDevice,
    toggleDevice,
    reloadDevice,
    batchCreate,
    getDeviceByAsset
  }
}, {
  persist: {
    key: 'xagent-devices-v1',
    storage: sessionStorage,
    // 只持久化设备列表，不持久化实时连接状态
    // 连接状态应在初始化时重新获取
    paths: ['devices']
  }
})
