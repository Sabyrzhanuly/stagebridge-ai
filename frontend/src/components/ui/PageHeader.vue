<template>
  <div class="page-header">
    <div class="page-header-main">
      <PageBackLink v-if="backTo" :to="backTo" :label="backLabel" />
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import PageBackLink from './PageBackLink.vue'

defineProps<{
  title: string
  subtitle?: string
  backTo?: RouteLocationRaw
  backLabel?: string
}>()
</script>
