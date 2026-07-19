<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>{{ t('conflicts.title') }}</h2>
        <p>{{ t('conflicts.findingCount', { count: conflicts.length }) }}</p>
      </div>
      <div class="segmented">
        <button v-for="option in filters" :key="option.value" :class="{ active: modelValue === option.value }" @click="$emit('update:modelValue', option.value)">
          {{ t(option.key) }}
        </button>
      </div>
    </div>
    <div class="conflict-list">
      <button
        v-for="conflict in filtered"
        :key="conflict.conflict_id"
        class="conflict-row"
        :class="{ selected: selectedId === conflict.conflict_id }"
        :aria-label="t('accessibility.openConflict', { name: translateCategory(conflict.category) })"
        @click="$emit('select', conflict.conflict_id)"
      >
        <span>
          <strong>{{ conflict.schema_name }}.{{ conflict.table_name }}</strong>
          <small>{{ labelFor(conflict) }}</small>
        </span>
        <StatusPill :label="conflict.severity" />
      </button>
    </div>
    <div v-if="!filtered.length" class="empty-state">{{ t('analysis.noConflicts') }}</div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Conflict } from '../types'
import StatusPill from './StatusPill.vue'
import { translateCategory } from '../i18n/formatters'

const props = defineProps<{
  conflicts: Conflict[]
  modelValue: string
  selectedId: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
  select: [value: string]
}>()

const { t } = useI18n()
const filters = [
  { value: 'All', key: 'conflicts.filters.all' },
  { value: 'Blocking', key: 'conflicts.filters.blocking' },
  { value: 'Warning', key: 'conflicts.filters.warning' }
]
const filtered = computed(() => (props.modelValue === 'All' ? props.conflicts : props.conflicts.filter(conflict => conflict.severity === props.modelValue)))

function labelFor(conflict: Conflict) {
  return conflict.column_name || conflict.constraint_name || translateCategory(conflict.category)
}
</script>
