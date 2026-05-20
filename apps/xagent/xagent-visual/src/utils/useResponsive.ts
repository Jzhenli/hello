import { ref, onMounted, onUnmounted, computed } from 'vue'

export type DeviceType = 'desktop' | 'tablet' | 'mobile'

export interface ResponsiveState {
  width: number
  height: number
  deviceType: DeviceType
  isDesktop: boolean
  isTablet: boolean
  isMobile: boolean
  isTouch: boolean
}

const breakpoints = {
  mobile: 768,
  tablet: 1024
}

function detectDeviceType(width: number): DeviceType {
  if (width < breakpoints.mobile) return 'mobile'
  if (width < breakpoints.tablet) return 'tablet'
  return 'desktop'
}

function detectTouch(): boolean {
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0
}

export function useResponsive() {
  const width = ref(window.innerWidth)
  const height = ref(window.innerHeight)
  const isTouch = ref(detectTouch())

  const deviceType = computed<DeviceType>(() => detectDeviceType(width.value))
  const isDesktop = computed(() => deviceType.value === 'desktop')
  const isTablet = computed(() => deviceType.value === 'tablet')
  const isMobile = computed(() => deviceType.value === 'mobile')

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
    isDesktop,
    isTablet,
    isMobile,
    isTouch
  }
}

let globalState: ResponsiveState | null = null

export function useResponsiveGlobal(): ResponsiveState {
  if (!globalState) {
    const width = ref(window.innerWidth)
    const height = ref(window.innerHeight)
    
    globalState = {
      width,
      height,
      deviceType: computed(() => detectDeviceType(width.value)) as unknown as DeviceType,
      isDesktop: computed(() => detectDeviceType(width.value) === 'desktop') as unknown as boolean,
      isTablet: computed(() => detectDeviceType(width.value) === 'tablet') as unknown as boolean,
      isMobile: computed(() => detectDeviceType(width.value) === 'mobile') as unknown as boolean,
      isTouch: detectTouch()
    }

    window.addEventListener('resize', () => {
      width.value = window.innerWidth
      height.value = window.innerHeight
    })
  }

  return globalState
}
