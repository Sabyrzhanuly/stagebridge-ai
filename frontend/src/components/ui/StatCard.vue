<template>
  <div class="stat-card" :class="[`stat-card--${variant}`, { 'stat-card--live': live }]">
    <div class="stat-card-orb" aria-hidden="true"></div>
    <div class="stat-card-top">
      <span class="stat-label">{{ label }}</span>
      <div class="stat-icon" :class="`stat-icon--${variant}`">
        <i :class="icon" aria-hidden="true"></i>
      </div>
    </div>
    <div class="stat-value">{{ value }}</div>
    <p v-if="hint" class="stat-hint">{{ hint }}</p>
    <span v-if="live" class="stat-live-dot" :title="t('ui.liveUpdating')" aria-hidden="true"></span>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

type StatVariant = 'blue' | 'green' | 'red' | 'amber' | 'slate' | 'accent'

withDefaults(defineProps<{
  label: string
  value: string | number
  icon: string
  variant?: StatVariant
  hint?: string
  live?: boolean
}>(), {
  variant: 'blue',
  live: false,
})
</script>
