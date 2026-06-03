import api from './index'

export interface Reading {
  asset: string
  timestamp: number
  service_name: string
  data: Record<string, unknown>
  tags: string[]
  standard_points: StandardPoint[]
  device_status: string | null
}

export interface StandardPoint {
  name: string
  point_name?: string
  value: number | boolean | string
  unit?: string
  data_type?: string
  quality?: string
  timestamp?: number
}

export interface ReadingsResponse {
  count: number
  readings: Reading[]
}

export const dataApi = {
  async getReadings(params?: {
    asset?: string
    start_time?: number
    end_time?: number
    limit?: number
    active_only?: boolean
  }): Promise<ReadingsResponse> {
    const res = await api.get('/api/data/readings', { params })
    return res.data
  },

  async getLatestReadings(asset: string, limit = 1): Promise<ReadingsResponse> {
    return this.getReadings({ asset, limit, active_only: false })
  },

  async getHistoryReadings(
    asset: string,
    startTime: number,
    endTime: number,
    limit = 1000
  ): Promise<ReadingsResponse> {
    return this.getReadings({
      asset,
      start_time: startTime,
      end_time: endTime,
      limit,
      active_only: false
    })
  },

  async deleteReadings(beforeTimestamp: number): Promise<{ success: boolean; deleted: number }> {
    const res = await api.delete('/api/data/readings', { params: { before_timestamp: beforeTimestamp } })
    return res.data
  },

  async getCollectionStats(params?: {
    start_time?: number
    end_time?: number
    interval?: 'hour' | 'day'
  }): Promise<{
    stats: Array<{ time: string; count: number; timestamp: number }>
    total_count: number
    avg_rate: number
  }> {
    const res = await api.get('/api/data/stats', { params })
    return res.data
  },

  async getDataQuality(): Promise<{
    good: number
    bad: number
    uncertain: number
    total: number
    quality_rate: number
  }> {
    const res = await api.get('/api/data/quality')
    return res.data
  }
}
