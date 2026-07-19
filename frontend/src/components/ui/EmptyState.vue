<template>
  <div class="empty-state" :class="{ compact }">
    <i v-if="icon" :class="icon" class="empty-state-icon" aria-hidden="true"></i>
    <div class="empty-state-title">{{ title }}</div>
    <p v-if="description" class="empty-state-desc">{{ description }}</p>
    <div v-if="$slots.action" class="empty-state-action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  icon?: string
  title: string
  description?: string
  compact?: boolean
}>(), {
  icon: 'fa-solid fa-inbox',
  compact: false,
})
</script>
