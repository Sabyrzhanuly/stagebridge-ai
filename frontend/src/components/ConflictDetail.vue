<template>
  <section class="panel detail-panel">
    <div v-if="conflict" class="detail-content">
      <div class="panel-header">
        <div>
          <h2>{{ translateCategory(conflict.category) }}</h2>
          <p>{{ conflict.schema_name }}.{{ conflict.table_name }} {{ conflict.column_name || conflict.constraint_name }}</p>
        </div>
        <StatusPill :label="conflict.severity" />
      </div>
      <div class="evidence-grid">
        <div>
          <span>{{ t('conflicts.affectedRows') }}</span>
          <strong>{{ conflict.affected_row_count }}</strong>
        </div>
        <div>
          <span>{{ t('conflicts.samples') }}</span>
          <strong>{{ sampleText }}</strong>
        </div>
        <div>
          <span>{{ t('conflicts.preflight') }}</span>
          <strong>{{ translateStatus(conflict.preflight_status) }}</strong>
        </div>
        <div>
          <span>{{ t('conflicts.breaking') }}</span>
          <strong>{{ t(conflict.breaking ? 'common.yes' : 'common.no') }}</strong>
        </div>
      </div>
      <div class="finding-explanation">
        <h3>{{ t('conflicts.why') }}</h3>
        <p>{{ localizedExplanation }}</p>
      </div>
      <div class="definition-grid">
        <div>
          <h3>{{ t('conflicts.production') }}</h3>
          <pre>{{ pretty(conflict.production_definition) }}</pre>
        </div>
        <div>
          <h3>{{ t('conflicts.development') }}</h3>
          <pre>{{ pretty(conflict.development_definition) }}</pre>
        </div>
      </div>
      <div>
        <h3>{{ t('conflicts.evidence') }}</h3>
        <pre>{{ pretty(conflict.evidence) }}</pre>
      </div>
      <div>
        <h3>{{ t('conflicts.sqlPreview') }}</h3>
        <pre>{{ localizedSqlPreview }}</pre>
      </div>
      <h3>{{ t('conflicts.strategies') }}</h3>
      <div class="strategy-row">
        <span v-for="strategy in localizedStrategies" :key="strategy">{{ strategy }}</span>
      </div>
    </div>
    <div v-else class="empty-state">{{ t('conflicts.select') }}</div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Conflict } from '../types'
import StatusPill from './StatusPill.vue'
import { translateCategory, translateStatus } from '../i18n/formatters'

const props = defineProps<{ conflict: Conflict | null }>()
const { t, te, tm } = useI18n()

const sampleText = computed(() => {
  if (!props.conflict?.sample_values?.length) return t('common.none')
  return props.conflict.sample_values.map(value => JSON.stringify(value)).join(', ')
})

const localizedExplanation = computed(() => {
  const key = `conflicts.explanations.${props.conflict?.category || ''}`
  return te(key) ? t(key) : t('conflicts.structuralDifference')
})

const localizedStrategies = computed(() => {
  const strategies = tm('conflicts.genericStrategies')
  return Array.isArray(strategies) ? strategies.map(String) : []
})

const localizedSqlPreview = computed(() => {
  const preview = props.conflict?.sql_preview?.trim() || ''
  if (!preview) return t('conflicts.noSqlPreview')
  return preview.startsWith('--') ? t('conflicts.reviewOnlySql') : preview
})

function pretty(value: unknown) {
  return JSON.stringify(value, (_key, item) => item === 'not present' ? t('common.notPresent') : item, 2)
}
</script>
