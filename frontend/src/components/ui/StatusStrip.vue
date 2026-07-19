<template>
  <div class="status-strip" role="status">
    <div class="status-strip-item">
      <template v-if="workerLoading">
        <i class="fa-solid fa-spinner fa-spin status-strip-spinner" aria-hidden="true"></i>
        <span class="status-strip-label">Celery Worker</span>
        <span class="status-strip-value status-strip-value--muted">{{ t('ui.checking') }}</span>
      </template>
      <template v-else>
        <span
          class="status-dot"
          :class="workerOnline ? 'status-dot--ok' : 'status-dot--danger'"
          aria-hidden="true"
        ></span>
        <span class="status-strip-label">Celery Worker</span>
        <span class="status-strip-value">{{ workerOnline ? 'Online' : 'Offline' }}</span>
        <span v-if="workerOnline && workerTaskCount > 0" class="status-strip-sub">
          · {{ t('ui.inQueue', { count: workerTaskCount }) }}
        </span>
      </template>
    </div>
    <div class="status-strip-divider" aria-hidden="true"></div>
    <div class="status-strip-item">
      <template v-if="monitoringLoading">
        <i class="fa-solid fa-spinner fa-spin status-strip-spinner" aria-hidden="true"></i>
        <span class="status-strip-label">{{ t('ui.monitoring') }}</span>
        <span class="status-strip-value status-strip-value--muted">{{ t('ui.connecting') }}</span>
      </template>
      <template v-else>
        <span
          class="status-dot"
          :class="monitoringLive ? 'status-dot--ok status-dot--pulse' : 'status-dot--danger'"
          aria-hidden="true"
        ></span>
        <span class="status-strip-label">{{ t('ui.monitoring') }}</span>
        <span class="status-strip-value">{{ monitoringLive ? 'Live' : 'Offline' }}</span>
      </template>
    </div>
    <div class="status-strip-divider" aria-hidden="true"></div>
    <div class="status-strip-item">
      <template v-if="serversLoading">
        <i class="fa-solid fa-spinner fa-spin status-strip-spinner" aria-hidden="true"></i>
        <span class="status-strip-label">{{ t('ui.serversCount') }}</span>
        <span class="status-strip-value status-strip-value--muted">{{ t('common.loading') }}</span>
      </template>
      <template v-else>
        <i class="fa-solid fa-server status-strip-icon" aria-hidden="true"></i>
        <span class="status-strip-label">{{ t('ui.serversCount') }}</span>
        <span class="status-strip-value text-mono">{{ serverCount }}</span>
      </template>
    </div>
    <div class="status-strip-divider" aria-hidden="true"></div>
    <button
      type="button"
      class="status-strip-item status-strip-item--clickable"
      :title="activeTasks > 0 ? t('ui.openTasks') : t('ui.tasks')"
      @click="emit('openTasks')"
    >
      <template v-if="tasksLoading">
        <i class="fa-solid fa-spinner fa-spin status-strip-spinner" aria-hidden="true"></i>
        <span class="status-strip-label">{{ t('ui.uiTasks') }}</span>
        <span class="status-strip-value status-strip-value--muted">{{ t('ui.syncing') }}</span>
      </template>
      <template v-else>
        <i class="fa-solid fa-list-check status-strip-icon" aria-hidden="true"></i>
        <span class="status-strip-label">{{ t('ui.uiTasks') }}</span>
        <span class="status-strip-value text-mono">{{ activeTasks }}</span>
      </template>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

withDefaults(defineProps<{
  workerOnline: boolean | null
  workerLoading?: boolean
  monitoringLive?: boolean | null
  monitoringLoading?: boolean
  serversLoading?: boolean
  serverCount: number
  tasksLoading?: boolean
  activeTasks: number
  workerTaskCount?: number
}>(), {
  workerLoading: false,
  monitoringLive: true,
  monitoringLoading: false,
  serversLoading: false,
  tasksLoading: false,
  workerTaskCount: 0,
})

const emit = defineEmits<{
  openTasks: []
}>()
</script>

<style scoped>
.status-strip-sub {
  font-size: 11px;
  color: #64748b;
  margin-left: 2px;
}

.status-strip-spinner {
  width: 12px;
  height: 12px;
  font-size: 12px;
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.status-strip-value--muted {
  font-weight: 500;
  color: var(--p-text-muted-color);
}

.status-strip-item--clickable {
  border: none;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: inherit;
  padding: 0;
  border-radius: 6px;
  transition: background 0.15s ease;
}

.status-strip-item--clickable:hover {
  background: rgba(3, 105, 161, 0.08);
}
</style>
