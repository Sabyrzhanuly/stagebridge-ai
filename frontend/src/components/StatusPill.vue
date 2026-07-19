<template>
  <span class="status-pill" :class="toneClass">{{ translatedLabel }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { translateStatus } from '../i18n/formatters'

const props = defineProps<{ label: string }>()
const translatedLabel = computed(() => translateStatus(props.label))

const toneClass = computed(() => {
  const value = props.label.toLowerCase()
  if (value.includes('blocking') || value.includes('failed')) return 'tone-blocking'
  if (value.includes('warning') || value.includes('approval') || value.includes('running')) return 'tone-warning'
  if (value.includes('passed') || value.includes('safe') || value.includes('completed')) return 'tone-safe'
  return 'tone-neutral'
})
</script>
