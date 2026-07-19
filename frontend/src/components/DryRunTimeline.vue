<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>{{ t('dryRun.title') }}</h2>
        <p>{{ t('dryRun.recordedSteps', { count: logs.length }) }}</p>
      </div>
      <StatusPill :label="statusLabel" />
    </div>
    <div class="timeline">
      <article v-for="log in logs" :key="log.id || log.sequence" class="timeline-step">
        <span class="sequence">{{ log.sequence }}</span>
        <div>
          <strong>{{ translateDryRunStep(log.step) }}</strong>
          <p>{{ localizedMessage(log) }}</p>
          <pre v-if="log.sql_preview">{{ log.sql_preview }}</pre>
        </div>
        <StatusPill :label="log.status" />
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { DryRunLog } from '../types'
import { useI18n } from 'vue-i18n'
import StatusPill from './StatusPill.vue'
import { translateDryRunStep } from '../i18n/formatters'

defineProps<{ logs: DryRunLog[]; statusLabel: string }>()
const { t, te } = useI18n()

function localizedMessage(log: DryRunLog): string {
  const key = `dryRun.messages.${log.step}`
  return te(key) ? t(key, { count: log.rows_affected }) : log.message
}
</script>
