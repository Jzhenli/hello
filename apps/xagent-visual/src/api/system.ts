import api from './index'
import type { SystemStatsResponse, DataQualityStats } from './types'

export const systemApi = {
  async getSystemStats(): Promise<SystemStatsResponse> {
    const res = await api.get('/api/system/stats')
    return res.data
  },

  async getDataQuality(): Promise<DataQualityStats> {
    const res = await api.get('/api/data/quality')
    return res.data
  },

  async getHealthCheck(): Promise<{
    status: 'healthy' | 'degraded' | 'unhealthy'
    checks: Record<string, { status: boolean; message: string }>
  }> {
    const res = await api.get('/api/system/health')
    return res.data
  }
}
