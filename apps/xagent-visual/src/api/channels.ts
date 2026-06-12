import api from './index'
import type {
  NorthChannelConfig,
  NorthChannelCreateResponse,
  NorthChannelUpdateResponse,
  NorthChannelListResponse,
  ConnectionTestRequest,
  ConnectionTestResponse,
  NorthChannelLogListResponse,
  NorthChannelStatus,
  NorthChannelProtocol
} from './types'

export const channelApi = {
  async list(params?: {
    status?: NorthChannelStatus
    protocol?: NorthChannelProtocol
    tags?: string[]
    enabled?: boolean
  }): Promise<NorthChannelListResponse> {
    const res = await api.get('/api/channels/', { params })
    return res.data
  },

  async get(id: string): Promise<NorthChannelConfig> {
    const res = await api.get(`/api/channels/${id}`)
    return res.data
  },

  async create(channel: NorthChannelConfig): Promise<NorthChannelCreateResponse> {
    const res = await api.post('/api/channels/', channel)
    return res.data
  },

  async update(id: string, updates: Partial<NorthChannelConfig>): Promise<NorthChannelUpdateResponse> {
    const res = await api.put(`/api/channels/${id}`, updates)
    return res.data
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/api/channels/${id}`)
  },

  async toggle(id: string): Promise<NorthChannelUpdateResponse> {
    const res = await api.post(`/api/channels/${id}/toggle`)
    return res.data
  },

  async testConnection(request: ConnectionTestRequest): Promise<ConnectionTestResponse> {
    const res = await api.post('/api/channels/test-connection', request)
    return res.data
  },

  async getStatistics(id: string): Promise<NorthChannelConfig['statistics']> {
    const res = await api.get(`/api/channels/${id}/statistics`)
    return res.data
  },

  async getLogs(id: string, params?: {
    level?: 'info' | 'warning' | 'error' | 'debug'
    limit?: number
    offset?: number
  }): Promise<NorthChannelLogListResponse> {
    const res = await api.get(`/api/channels/${id}/logs`, { params })
    return res.data
  },

  async restart(id: string): Promise<{ success: boolean; message: string }> {
    const res = await api.post(`/api/channels/${id}/restart`)
    return res.data
  },

  async batchCreate(channels: NorthChannelConfig[]): Promise<{
    total: number
    succeeded: number
    failed: number
    details: Array<{ id: string; success: boolean; message: string }>
  }> {
    const res = await api.post('/api/channels/batch', channels)
    return res.data
  },

  async exportChannels(ids?: string[]): Promise<{ channels: NorthChannelConfig[] }> {
    const data = ids ? { channel_ids: ids } : {}
    const res = await api.post('/api/channels/export', data)
    return res.data
  },

  async importChannels(data: Record<string, unknown>, overwrite = false): Promise<{
    total: number
    succeeded: number
    failed: number
    details: Array<{ id: string; success: boolean; message: string }>
  }> {
    const res = await api.post('/api/channels/import', data, { params: { overwrite } })
    return res.data
  },

  async listAdapters(): Promise<{
    adapters: Array<{
      name: string
      customer_code: string | null
      description: string
      has_defaults: boolean
    }>
  }> {
    const res = await api.get('/api/channels/adapters/list')
    return res.data
  },

  async getAdapterDefaults(adapterCode: string): Promise<{
    adapter_code: string
    adapter_name: string
    defaults: Record<string, any>
  }> {
    const res = await api.get(`/api/channels/adapters/${adapterCode}/defaults`)
    return res.data
  }
}
