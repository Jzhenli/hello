import api from './index'
import type {
  DeviceConfig,
  DeviceCreateResponse,
  DeviceUpdateResponse,
  PointConfig,
  PointCreateResponse,
  DeviceListResponse,
  BatchOperationResult,
  DeviceReloadResponse,
  DeviceStatus
} from './types'

export const deviceApi = {
  async list(params?: {
    status?: DeviceStatus
    plugin_name?: string
    tags?: string[]
    enabled?: boolean
  }): Promise<DeviceListResponse> {
    const res = await api.get('/api/devices/', { params })
    return res.data
  },

  async getLatest(activeOnly = true): Promise<{ count: number; devices: any[] }> {
    const res = await api.get('/api/devices/latest', { params: { active_only: activeOnly } })
    return res.data
  },

  async getConnectionStatus(): Promise<Record<string, string>> {
    const res = await api.get('/api/devices/connection-status')
    return res.data
  },

  async get(asset: string): Promise<DeviceConfig> {
    const res = await api.get(`/api/devices/${asset}`)
    return res.data
  },

  async create(device: DeviceConfig): Promise<DeviceCreateResponse> {
    const res = await api.post('/api/devices/', device)
    return res.data
  },

  async update(asset: string, updates: Record<string, unknown>): Promise<DeviceUpdateResponse> {
    const res = await api.put(`/api/devices/${asset}`, updates)
    return res.data
  },

  async delete(asset: string): Promise<void> {
    await api.delete(`/api/devices/${asset}`)
  },

  async addPoint(asset: string, point: PointConfig): Promise<PointCreateResponse> {
    const res = await api.post(`/api/devices/${asset}/points`, point)
    return res.data
  },

  async listPoints(asset: string): Promise<PointConfig[]> {
    const res = await api.get(`/api/devices/${asset}/points`)
    return res.data
  },

  async updatePoint(asset: string, pointName: string, updates: Record<string, unknown>): Promise<PointCreateResponse> {
    const res = await api.put(`/api/devices/${asset}/points/${pointName}`, updates)
    return res.data
  },

  async removePoint(asset: string, pointName: string): Promise<void> {
    await api.delete(`/api/devices/${asset}/points/${pointName}`)
  },

  async batchCreate(devices: DeviceConfig[]): Promise<BatchOperationResult> {
    const res = await api.post('/api/devices/batch', devices)
    return res.data
  },

  async reload(asset: string): Promise<DeviceReloadResponse> {
    const res = await api.post(`/api/devices/${asset}/reload`)
    return res.data
  },

  async reloadAll(assets?: string[]): Promise<DeviceReloadResponse> {
    const res = await api.post('/api/devices/reload', assets)
    return res.data
  },

  async exportDevices(assets?: string[]): Promise<Record<string, unknown>> {
    const res = await api.post('/api/devices/export', assets)
    return res.data
  },

  async importDevices(data: Record<string, unknown>, overwrite = false): Promise<BatchOperationResult> {
    const res = await api.post('/api/devices/import', data, { params: { overwrite } })
    return res.data
  }
}
