<template>
  <div class="alert-banner" :class="`alert-banner--${severity}`" role="alert">
    <i :class="iconClass" class="alert-banner-icon" aria-hidden="true"></i>
    <div class="alert-banner-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type AlertSeverity = 'warn' | 'danger' | 'info'

const props = withDefaults(defineProps<{
  severity?: AlertSeverity
  icon?: string
}>(), {
  severity: 'warn',
})

const iconClass = computed(() => {
  if (props.icon) return props.icon
  if (props.severity === 'danger') return 'fa-solid fa-circle-xmark'
  if (props.severity === 'info') return 'fa-solid fa-circle-info'
  return 'fa-solid fa-triangle-exclamation'
})
</script>
