<template>
  <section class="metric-strip">
    <div v-for="metric in metrics" :key="metric.label" class="metric">
      <span>{{ metric.label }}</span>
      <strong>{{ metric.value }}</strong>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  metrics: Array<{ label: string; value: string | number }>
}>()
</script>

