import { ref, onMounted, onUnmounted, computed, type ComputedRef } from 'vue'

export type DeviceType = 'desktop' | 'tablet' | 'mobile'
export type TabletSize = 'small' | 'medium' | 'large' | 'none'

export interface ResponsiveState {
  width: number | Ref<number>
  height: number | Ref<number>
  deviceType: DeviceType | ComputedRef<DeviceType>
  tabletSize: TabletSize | ComputedRef<TabletSize>
  isDesktop: boolean | ComputedRef<boolean>
  isTablet: boolean | ComputedRef<boolean>
  isMobile: boolean | ComputedRef<boolean>
  isSmallTablet: boolean | ComputedRef<boolean>
  isMediumTablet: boolean | ComputedRef<boolean>
  isLargeTablet: boolean | ComputedRef<boolean>
  isTouch: boolean
}

import type { Ref } from 'vue'

// 优化的断点设置
const breakpoints = {
  mobile: 768,
  tabletSmall: 1024,    // 1024×600 平板
  tabletMedium: 1366,   // 1280×800 平板
  tabletLarge: 1920     // 1920×1080 平板
}

function detectDeviceType(width: number, height: number): DeviceType {
  if (width < breakpoints.mobile) return 'mobile'

  // 检测是否为小平板（1024×600）
  if (width >= breakpoints.tabletSmall && width < breakpoints.tabletMedium) {
    // 如果高度小于700，认为是小平板，使用平板布局
    if (height < 700) return 'tablet'
  }

  if (width < breakpoints.tabletMedium) return 'tablet'
  return 'desktop'
}

function detectTabletSize(width: number, height: number, deviceType: DeviceType): TabletSize {
  // 只有平板设备才判断尺寸
  if (deviceType !== 'tablet') return 'none'
  
  if (width < breakpoints.tabletSmall) return 'none'

  // 小平板：1024×600
  if (width >= breakpoints.tabletSmall && width < breakpoints.tabletMedium) {
    if (height < 700) return 'small'
    return 'medium'
  }

  // 中平板：1280×800
  if (width >= breakpoints.tabletMedium && width < breakpoints.tabletLarge) {
    return 'medium'
  }

  // 大平板：1920×1080
  if (width >= breakpoints.tabletLarge) {
    return 'large'
  }

  return 'none'
}

function detectTouch(): boolean {
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0
}

export function useResponsive() {
  const width = ref(window.innerWidth)
  const height = ref(window.innerHeight)
  const isTouch = ref(detectTouch())

  const deviceType = computed<DeviceType>(() => detectDeviceType(width.value, height.value))
  const tabletSize = computed<TabletSize>(() => detectTabletSize(width.value, height.value, deviceType.value))

  const isDesktop = computed(() => deviceType.value === 'desktop')
  const isTablet = computed(() => deviceType.value === 'tablet')
  const isMobile = computed(() => deviceType.value === 'mobile')

  const isSmallTablet = computed(() => tabletSize.value === 'small')
  const isMediumTablet = computed(() => tabletSize.value === 'medium')
  const isLargeTablet = computed(() => tabletSize.value === 'large')

  const updateSize = () => {
    width.value = window.innerWidth
    height.value = window.innerHeight
  }

  onMounted(() => {
    window.addEventListener('resize', updateSize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateSize)
  })

  return {
    width,
    height,
    deviceType,
    tabletSize,
    isDesktop,
    isTablet,
    isMobile,
    isSmallTablet,
    isMediumTablet,
    isLargeTablet,
    isTouch
  }
}

let globalState: ResponsiveState | null = null

export function useResponsiveGlobal(): ResponsiveState {
  if (!globalState) {
    const width = ref(window.innerWidth)
    const height = ref(window.innerHeight)

    const deviceType = computed(() => detectDeviceType(width.value, height.value))

    globalState = {
      width,
      height,
      deviceType,
      tabletSize: computed(() => detectTabletSize(width.value, height.value, deviceType.value)),
      isDesktop: computed(() => detectDeviceType(width.value, height.value) === 'desktop'),
      isTablet: computed(() => detectDeviceType(width.value, height.value) === 'tablet'),
      isMobile: computed(() => detectDeviceType(width.value, height.value) === 'mobile'),
      isSmallTablet: computed(() => detectTabletSize(width.value, height.value, deviceType.value) === 'small'),
      isMediumTablet: computed(() => detectTabletSize(width.value, height.value, deviceType.value) === 'medium'),
      isLargeTablet: computed(() => detectTabletSize(width.value, height.value, deviceType.value) === 'large'),
      isTouch: detectTouch()
    }

    window.addEventListener('resize', () => {
      width.value = window.innerWidth
      height.value = window.innerHeight
    })
  }

  return globalState
}
