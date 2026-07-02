import { ref, computed, watch, onMounted, onUnmounted, type Ref } from 'vue'
import type { PointBinding } from '@/types/scada'
import { usePointStore } from '@/stores/points'
import { useScadaStore } from '@/stores/scada'
import type { PointDisplay } from '@/stores/points'

export interface UseComponentBindingOptions {
  /** 是否启用自动刷新（轮询） */
  autoRefresh?: boolean
  /** 轮询间隔（毫秒），默认 5000ms */
  refreshInterval?: number
  /** 值转换器，用于将原始值转换为组件需要的格式 */
  transform?: (value: any, point: PointDisplay | null) => any
}

export interface UseComponentBindingReturn {
  /** 当前绑定值 */
  currentValue: Ref<any>
  /** 绑定的点位信息 */
  boundPoint: Ref<PointDisplay | null>
  /** 绑定是否有效 */
  isValid: Ref<boolean>
  /** 手动刷新数据 */
  refresh: () => void
  /** 写入值 */
  writeValue: (value: any) => Promise<{ success: boolean; message: string }>
}

/**
 * 组件绑定 composable
 * 统一管理组件与数据点位的绑定关系，提供读值、监听、写入功能
 */
export function useComponentBinding(
  binding: Ref<PointBinding | null>,
  options: UseComponentBindingOptions = {}
): UseComponentBindingReturn {
  const {
    autoRefresh = false,
    refreshInterval = 5000,
    transform
  } = options

  const pointStore = usePointStore()
  const scadaStore = useScadaStore()

  const currentValue = ref<any>(null)
  const boundPoint = ref<PointDisplay | null>(null)
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  const findBoundPoint = (): PointDisplay | null => {
    if (!binding.value) return null

    const device = pointStore.devices.find(
      d => d.asset === binding.value!.deviceId || d.name === binding.value!.deviceId
    )
    if (!device) return null

    return device.points.find(p => p.name === binding.value!.pointName) || null
  }

  const updateValue = () => {
    // 编辑模式下不读取真实数据，返回默认值
    if (scadaStore.isEditing) {
      currentValue.value = transform ? transform(null, null) : null
      boundPoint.value = null
      return
    }

    const point = findBoundPoint()
    boundPoint.value = point

    if (point) {
      currentValue.value = transform
        ? transform(point.currentValue, point)
        : point.currentValue
    } else {
      currentValue.value = null
    }
  }

  watch(
    () => pointStore.devices,
    () => {
      updateValue()
    },
    { deep: true }
  )

  watch(binding, () => {
    updateValue()
  })

  // 监听编辑模式变化
  watch(() => scadaStore.isEditing, () => {
    updateValue()
    if (scadaStore.isEditing) {
      stopAutoRefresh()
    } else {
      startAutoRefresh()
    }
  })

  const startAutoRefresh = () => {
    if (scadaStore.isEditing) return
    if (autoRefresh && binding.value) {
      refreshTimer = setInterval(() => {
        pointStore.fetchDevicePoints(binding.value!.deviceId)
      }, refreshInterval)
    }
  }

  const stopAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  const refresh = async () => {
    if (scadaStore.isEditing) return
    if (binding.value) {
      await pointStore.fetchDevicePoints(binding.value.deviceId)
    }
  }

  const writeValue = async (value: any): Promise<{ success: boolean; message: string }> => {
    if (!binding.value || !boundPoint.value) {
      return { success: false, message: '未绑定有效点位' }
    }

    if (!boundPoint.value.writable) {
      return { success: false, message: `点位 ${binding.value.pointName} 不可写` }
    }

    return pointStore.writePoint(
      binding.value.deviceId,
      binding.value.pointName,
      value
    )
  }

  onMounted(() => {
    updateValue()
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
  })

  const isValid = computed(() => boundPoint.value !== null)

  return {
    currentValue,
    boundPoint,
    isValid,
    refresh,
    writeValue
  }
}
