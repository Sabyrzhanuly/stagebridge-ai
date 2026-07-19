<template>
  <div v-if="tasks.length" class="worker-activity card-panel">
    <div class="card-panel-title">
      <span>
        <i class="fa-solid fa-gears" aria-hidden="true"></i>
        {{ t('ui.workerRunning') }}
      </span>
      <Button size="small" text severity="secondary" @click="emit('openTasks')">
        {{ t('ui.openTasks') }}
      </Button>
    </div>
    <ul class="worker-activity-list">
      <li v-for="task in tasks" :key="task.task_id + task.worker" class="worker-activity-row">
        <i class="fa-solid fa-spinner fa-spin worker-activity-spin" aria-hidden="true"></i>
        <span class="worker-activity-name">{{ formatTaskName(task.name) }}</span>
        <span class="worker-activity-meta muted">{{ task.worker.split('@')[0] }}</span>
        <span v-if="taskDetail(task)" class="worker-activity-detail">{{ taskDetail(task) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import type { CeleryQueueTask } from '../../stores/health'

const { t } = useI18n()

defineProps<{
  tasks: CeleryQueueTask[]
}>()

const emit = defineEmits<{
  openTasks: []
}>()

function formatTaskName(name: string): string {
  if (name.includes('run_backup')) return t('ui.taskBackup')
  if (name.includes('run_restore')) return 'Restore'
  if (name.includes('run_scenario')) return t('ui.taskScenario')
  if (name.includes('pg_client')) return 'PG client'
  if (name.includes('collect_org_metrics')) return t('ui.taskMetrics')
  if (name.includes('check_org_alert')) return t('ui.taskAlerts')
  const short = name.split('.').pop() || name
  return short.replace(/_/g, ' ')
}

function taskDetail(task: CeleryQueueTask): string {
  const args = task.args || []
  if (task.name.includes('run_backup') && args.length >= 2) {
    return `server #${args[0]}, ${args[1]}`
  }
  if (task.name.includes('run_restore') && args.length >= 2) {
    return `server #${args[0]}, ${args[1]}`
  }
  return ''
}
</script>

<style scoped>
.worker-activity {
  margin-bottom: 16px;
}

.card-panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.worker-activity-list {
  list-style: none;
  margin: 0;
  padding: 8px 12px 12px;
}

.worker-activity-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
}

.worker-activity-row:last-child {
  border-bottom: none;
}

.worker-activity-spin {
  color: #0369a1;
  width: 14px;
  flex-shrink: 0;
}

.worker-activity-name {
  font-weight: 600;
}

.worker-activity-meta {
  font-size: 11px;
}

.worker-activity-detail {
  margin-left: auto;
  font-size: 11px;
  color: #64748b;
  font-family: ui-monospace, monospace;
}
</style>
