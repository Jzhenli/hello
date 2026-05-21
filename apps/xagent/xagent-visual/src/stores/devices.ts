import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { deviceApi } from '@/api/devices'
import type { DeviceConfig, DeviceStatus, BatchOperationResult } from '@/api/types'

export interface DeviceListItem {
  asset: string
  name: string
  enabled: boolean
  status: DeviceStatus
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

function mapDeviceToListItem(device: DeviceConfig): DeviceListItem {
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
    pluginConfig: pluginConfig as Record<string, unknown>,
    tags: device.tags || [],
    created_at: device.created_at,
    updated_at: device.updated_at
  }
}

export const useDeviceStore = defineStore('devices', () => {
  const devices = ref<DeviceConfig[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const deviceList = computed<DeviceListItem[]>(() =>
    devices.value.map(mapDeviceToListItem)
  )

  const onlineDevices = computed(() =>
    deviceList.value.filter(d => d.status === 'active' && d.enabled).length
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
    fetchDevices,
    createDevice,
    updateDevice,
    deleteDevice,
    toggleDevice,
    reloadDevice,
    batchCreate,
    getDeviceByAsset
  }
})
