<template>
  <div class="server-mobile-list">
    <div v-if="loading" class="server-mobile-loading">
      <ProgressSpinner style="width: 32px; height: 32px" stroke-width="4" />
    </div>

    <EmptyState
      v-else-if="!servers.length"
      icon="fa-solid fa-server"
      :title="t('serverActions.emptyTitle')"
      :description="t('serverActions.emptyDesc')"
      compact
    >
      <template #action>
        <slot name="empty-action" />
      </template>
    </EmptyState>

    <article
      v-for="server in servers"
      :key="server.id"
      class="server-mobile-card"
    >
      <div class="server-mobile-card-head">
        <button type="button" class="server-mobile-card-title" @click="emit('open', server.id)">
          {{ server.name }}
        </button>
        <Tag
          :severity="server.is_active ? 'success' : 'danger'"
          :value="serverActiveLabel(server.is_active)"
        />
      </div>

      <div class="server-mobile-card-host text-mono">
        {{ server.host }}:{{ server.port }}
      </div>

      <div class="server-mobile-card-meta">
        <Tag :severity="envSeverity(server.environment)" :value="server.environment" />
        <span
          v-if="server.pg_major_version"
          class="pg-version-badge"
        >v{{ server.pg_major_version }}</span>
        <span class="muted server-mobile-card-user">{{ server.admin_user }}</span>
      </div>

      <div class="server-mobile-card-actions">
        <ServerRowActions
          :testing="testingId === server.id"
          @open="emit('open', server.id)"
          @edit="emit('edit', server.id)"
          @roles="emit('navigate', server.id, 'roles')"
          @databases="emit('navigate', server.id, 'databases')"
          @monitoring="emit('navigate', server.id, 'monitoring')"
          @diagnostics="emit('navigate', server.id, 'diagnostics')"
          @test="emit('test', server.id)"
          @delete="emit('delete', server.id)"
        />
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import EmptyState from '../ui/EmptyState.vue'
import ServerRowActions from './ServerRowActions.vue'
import type { Server } from '../../api/types'
import { envSeverity, serverActiveLabel } from '../../utils/tags'

const { t } = useI18n()

defineProps<{
  servers: Server[]
  loading?: boolean
  testingId?: number | null
}>()

const emit = defineEmits<{
  open: [id: number]
  edit: [id: number]
  navigate: [id: number, route: string]
  test: [id: number]
  delete: [id: number]
}>()
</script>
