import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Device {
  name: string
  enabled: boolean
  assetName: string
  protocol: string
  status: 'online' | 'offline'
  pointCount: number
  lastUpdate: string
  connection: {
    host: string
    port: number
  }
}

export interface NorthChannel {
  name: string
  enabled: boolean
  protocol: string
  status: 'online' | 'offline'
  uploadedCount: number
  connection: {
    url?: string
    host?: string
    port?: number
  }
}

export const useDeviceStore = defineStore('devices', () => {
  const southDevices = ref<Device[]>([
    {
      name: 'KNX-01',
      enabled: true,
      assetName: 'knx_building',
      protocol: 'KNX',
      status: 'online',
      pointCount: 128,
      lastUpdate: '2分钟前',
      connection: { host: '192.168.1.100', port: 3671 }
    },
    {
      name: 'MODBUS-01',
      enabled: true,
      assetName: 'modbus_plant',
      protocol: 'Modbus TCP',
      status: 'online',
      pointCount: 64,
      lastUpdate: '1分钟前',
      connection: { host: '192.168.1.101', port: 502 }
    },
    {
      name: 'BACNET-01',
      enabled: false,
      assetName: 'bacnet_hvac',
      protocol: 'BACnet',
      status: 'offline',
      pointCount: 32,
      lastUpdate: '连接失败',
      connection: { host: '192.168.1.102', port: 47808 }
    },
    {
      name: 'KNX-02',
      enabled: true,
      assetName: 'knx_floor2',
      protocol: 'KNX',
      status: 'online',
      pointCount: 96,
      lastUpdate: '30秒前',
      connection: { host: '192.168.1.103', port: 3671 }
    }
  ])

  const northChannels = ref<NorthChannel[]>([
    {
      name: 'MQTT通道',
      enabled: true,
      protocol: 'MQTT',
      status: 'online',
      uploadedCount: 12456,
      connection: { url: 'mqtt.example.com' }
    },
    {
      name: 'XNC通道',
      enabled: true,
      protocol: 'XNC',
      status: 'online',
      uploadedCount: 8234,
      connection: { host: '192.168.1.200', port: 8080 }
    }
  ])

  const onlineDevices = computed(() => 
    southDevices.value.filter(d => d.status === 'online').length
  )
  
  const totalDevices = computed(() => southDevices.value.length)
  
  const totalPoints = computed(() => 
    southDevices.value.reduce((sum, d) => sum + d.pointCount, 0)
  )

  const toggleDevice = (name: string) => {
    const device = southDevices.value.find(d => d.name === name)
    if (device) {
      device.enabled = !device.enabled
      device.status = device.enabled ? 'online' : 'offline'
    }
  }

  const toggleChannel = (name: string) => {
    const channel = northChannels.value.find(c => c.name === name)
    if (channel) {
      channel.enabled = !channel.enabled
      channel.status = channel.enabled ? 'online' : 'offline'
    }
  }

  return {
    southDevices,
    northChannels,
    onlineDevices,
    totalDevices,
    totalPoints,
    toggleDevice,
    toggleChannel
  }
})
