<template>
  <span v-if="type === 'mono-line'" class="fa-stack pointer" :style="sizeStyle">
    <i
      :class="['xicon_' + name + '_TL']"
      class="fa-stack-1x"
      :style="[fontSizeStyle, { color: color?.normal || 'var(--color-primary)' }]"
    ></i>
  </span>
  <span v-else-if="type === 'color-white'" class="fa-stack pointer" :style="sizeStyle">
    <i
      :class="['xicon_' + name + '_TF']"
      class="fa-stack-1x"
      :style="[fontSizeStyle, { color: color?.normal || 'var(--color-primary)' }]"
    ></i>
  </span>

  <div
    v-else-if="type === 'mono-filled'"
    style="display: inline-block; text-align: center; margin: 0 6px; background-clip: text"
    class="btn-menu active"
    :style="sizeStyle"
  >
    <span :class="['xicon_' + name + '_TF']" :style="[fontSizeStyle, { color: 'transparent' }]"></span>
  </div>
  <span v-else class="fa-stack pointer" :style="sizeStyle">
    <i
      :class="['xicon_' + name + '_FL']"
      class="fa-stack-1x"
      :style="[fontSizeStyle, { color: 'var(--color-font-default)' }]"
    ></i>
    <i
      :class="['xicon_' + name + '_HL']"
      class="fa-stack-1x"
      :style="[fontSizeStyle, { color: color?.normal || 'var(--color-primary)' }]"
    ></i>
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    active?: boolean
    disabled?: boolean
    size?: number
    type?: 'default' | 'menu' | 'mono-line' | 'mono-filled' | 'color-white' | 'no-background'
    color?: {
      normal: string
      active?: string
      disabled?: string
      activeDisabled?: string
    }
    title?: string
  }>(),
  {
    size: 32,
    type: 'default'
  }
)

const sizeStyle = computed(() => {
  return {
    width: props.size + 'px',
    height: props.size + 'px',
    'line-height': props.size + 'px'
  }
})

const fontSizeStyle = computed(() => {
  return { 'font-size': props.size + 'px' }
})
</script>

<style lang="scss" scoped>
.pointer {
  cursor: pointer;
}
</style>
