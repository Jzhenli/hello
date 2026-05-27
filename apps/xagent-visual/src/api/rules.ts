import api from './index'
import type {
  RuleResponse,
  RuleListResponse,
  RuleCreateRequest,
  RuleUpdateRequest,
  RuleOperationResponse,
  RuleEngineStatusResponse,
  AlertListResponse
} from './types'

export interface ChannelCreateRequest {
  channel_id: string
  plugin_name: string
  config: Record<string, any>
}

export const ruleApi = {
  async list(): Promise<RuleListResponse> {
    const res = await api.get('/api/rules')
    return res.data
  },

  async get(ruleId: string): Promise<RuleResponse> {
    const res = await api.get(`/api/rules/${ruleId}`)
    return res.data
  },

  async create(data: RuleCreateRequest): Promise<RuleOperationResponse> {
    const res = await api.post('/api/rules', data)
    return res.data
  },

  async update(ruleId: string, data: RuleUpdateRequest): Promise<RuleOperationResponse> {
    const res = await api.put(`/api/rules/${ruleId}`, data)
    return res.data
  },

  async remove(ruleId: string): Promise<RuleOperationResponse> {
    const res = await api.delete(`/api/rules/${ruleId}`)
    return res.data
  },

  async getStatus(): Promise<RuleEngineStatusResponse> {
    const res = await api.get('/api/rules/status')
    return res.data
  },

  async createChannel(data: ChannelCreateRequest): Promise<any> {
    const res = await api.post('/api/rules/channels', data)
    return res.data
  },

  async removeChannel(channelId: string): Promise<any> {
    const res = await api.delete(`/api/rules/channels/${channelId}`)
    return res.data
  },

  async bindRuleChannels(ruleId: string, channelIds: string[]): Promise<any> {
    const res = await api.post(`/api/rules/${ruleId}/channels`, { channel_ids: channelIds })
    return res.data
  },

  async listAlerts(): Promise<AlertListResponse> {
    const res = await api.get('/api/rules/alerts')
    return res.data
  },

  async acknowledgeAlert(alertId: string): Promise<RuleOperationResponse> {
    const res = await api.post(`/api/rules/alerts/${alertId}/acknowledge`)
    return res.data
  },

  async resolveAlert(alertId: string): Promise<RuleOperationResponse> {
    const res = await api.post(`/api/rules/alerts/${alertId}/resolve`)
    return res.data
  },

  async ignoreAlert(alertId: string): Promise<RuleOperationResponse> {
    const res = await api.post(`/api/rules/alerts/${alertId}/ignore`)
    return res.data
  },

  async clearResolvedAlerts(): Promise<RuleOperationResponse> {
    const res = await api.delete('/api/rules/alerts/cleared')
    return res.data
  }
}
