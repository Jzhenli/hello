import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { channelApi } from '@/api/channels'
import type { NorthChannelConfig, NorthChannelStatus, NorthChannelProtocol } from '@/api/types'

export interface ChannelListItem {
  id: string
  name: string
  enabled: boolean
  status: NorthChannelStatus
  protocol: NorthChannelProtocol
  connectionStatus: 'online' | 'offline' | 'error' | 'unknown'
  host: string
  port: number
  uploadRate: number
  successRate: number
  backlogCount: number
  tags: string[]
  created_at?: string
  updated_at?: string
}

function mapChannelToListItem(channel: NorthChannelConfig): ChannelListItem {
  // 从扁平的连接配置中获取 host 和 port
  let host = ''
  let port = 0
  
  if (channel.protocol === 'mqtt') {
    host = channel.connection.broker || ''
    port = channel.connection.port || 1883
  } else if (channel.protocol === 'xnc') {
    host = channel.connection.remote_host || ''
    port = channel.connection.remote_port || 9000
  } else if (channel.protocol === 'http') {
    try {
      const url = new URL(channel.connection.endpoint || '')
      host = url.hostname
      port = parseInt(url.port) || (url.protocol === 'https:' ? 443 : 80)
    } catch {
      host = channel.connection.endpoint || ''
      port = 80
    }
  }
  
  return {
    id: channel.id,
    name: channel.name,
    enabled: channel.enabled,
    status: channel.status,
    protocol: channel.protocol,
    connectionStatus: channel.status,
    host,
    port,
    uploadRate: channel.statistics?.upload_rate || 0,
    successRate: channel.statistics?.success_rate || 0,
    backlogCount: channel.statistics?.backlog_count || 0,
    tags: channel.tags || [],
    created_at: channel.created_at,
    updated_at: channel.updated_at
  }
}

export const useChannelStore = defineStore('channels', () => {
  const channels = ref<NorthChannelConfig[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const channelList = computed<ChannelListItem[]>(() =>
    channels.value.map(mapChannelToListItem)
  )

  const onlineChannels = computed(() =>
    channelList.value.filter(c => c.connectionStatus === 'online').length
  )

  const totalChannels = computed(() => channels.value.length)

  const totalUploadRate = computed(() =>
    channelList.value.reduce((sum, c) => sum + c.uploadRate, 0)
  )

  const totalBacklog = computed(() =>
    channelList.value.reduce((sum, c) => sum + c.backlogCount, 0)
  )

  const averageSuccessRate = computed(() => {
    const enabledChannels = channelList.value.filter(c => c.enabled)
    if (enabledChannels.length === 0) return 0
    const totalRate = enabledChannels.reduce((sum, c) => sum + c.successRate, 0)
    return Math.round(totalRate / enabledChannels.length)
  })

  const errorChannels = computed(() =>
    channelList.value.filter(c => c.connectionStatus === 'error').length
  )

  async function fetchChannels() {
    loading.value = true
    error.value = null
    try {
      const res = await channelApi.list()
      channels.value = res.channels
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '获取通道列表失败'
      error.value = msg
      console.error('Failed to fetch channels:', e)
    } finally {
      loading.value = false
    }
  }

  async function createChannel(channel: NorthChannelConfig) {
    const res = await channelApi.create(channel)
    if (res.success) {
      await fetchChannels()
    }
    return res
  }

  async function updateChannel(id: string, updates: Partial<NorthChannelConfig>) {
    const res = await channelApi.update(id, updates)
    if (res.success) {
      await fetchChannels()
    }
    return res
  }

  async function deleteChannel(id: string) {
    await channelApi.delete(id)
    await fetchChannels()
  }

  async function toggleChannel(id: string) {
    const res = await channelApi.toggle(id)
    if (res.success) {
      await fetchChannels()
    }
    return res
  }

  async function testConnection(id: string) {
    const channel = channels.value.find(c => c.id === id)
    if (!channel) {
      throw new Error('通道不存在')
    }
    return await channelApi.testConnection({
      channel_id: id,
      connection: channel.connection,
      protocol: channel.protocol
    })
  }

  async function restartChannel(id: string) {
    return await channelApi.restart(id)
  }

  async function getChannelStatistics(id: string) {
    return await channelApi.getStatistics(id)
  }

  function getChannelById(id: string): NorthChannelConfig | undefined {
    return channels.value.find(c => c.id === id)
  }

  return {
    channels,
    channelList,
    loading,
    error,
    onlineChannels,
    totalChannels,
    totalUploadRate,
    totalBacklog,
    averageSuccessRate,
    errorChannels,
    fetchChannels,
    createChannel,
    updateChannel,
    deleteChannel,
    toggleChannel,
    testConnection,
    restartChannel,
    getChannelStatistics,
    getChannelById
  }
}, {
  persist: {
    key: 'xagent-channels-v1',
    storage: sessionStorage,
    paths: ['channels']
  }
})
