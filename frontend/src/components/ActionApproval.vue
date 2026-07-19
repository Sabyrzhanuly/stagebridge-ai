<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>{{ t('actions.title') }}</h2>
        <p>{{ t('actions.approvedCount', { approved: approvedCount, total: actions.length }) }}</p>
      </div>
      <button class="icon-button" :title="t('actions.approveAll')" @click="$emit('approveAll')">
        <CheckCheck :size="18" />
      </button>
    </div>
    <div class="action-list">
      <article v-for="action in actions" :key="action.id" class="action-item">
        <label class="toggle">
          <input type="checkbox" :checked="action.approved" :aria-label="t('accessibility.approveAction', { action: translateAction(action.action_type) })" @change="$emit('toggle', action.id, !action.approved)" />
          <span></span>
        </label>
        <div>
          <strong>{{ translateAction(action.action_type) }}</strong>
          <p>{{ localizedRationale(action) }}</p>
          <pre>{{ localizedPreview(action) }}</pre>
        </div>
        <StatusPill :label="action.approved ? 'approved' : 'pending'" />
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckCheck } from '@lucide/vue'
import type { ApprovedAction } from '../types'
import StatusPill from './StatusPill.vue'
import { translateAction } from '../i18n/formatters'

const props = defineProps<{ actions: ApprovedAction[] }>()
const { t, te } = useI18n()
defineEmits<{
  toggle: [id: number, approved: boolean]
  approveAll: []
}>()

const approvedCount = computed(() => props.actions.filter(action => action.approved).length)

function localizedRationale(action: ApprovedAction): string {
  const key = `actions.rationales.${action.action_type}`
  return te(key) ? t(key) : action.rationale
}

function localizedPreview(action: ApprovedAction): string {
  if (!action.sql_preview.trim().startsWith('--')) return action.sql_preview
  const key = `actions.previews.${action.action_type}`
  return te(key) ? t(key) : t('conflicts.reviewOnlySql')
}
</script>
