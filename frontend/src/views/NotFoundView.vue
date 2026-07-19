<template>
  <div class="card-panel not-found-panel">
    <EmptyState
      icon="fa-solid fa-compass"
      :title="t('notFound.title')"
      :description="t('notFound.desc')"
    >
      <template #action>
        <Button @click="router.push('/')">
          <i class="fa-solid fa-house btn-icon-left" aria-hidden="true"></i>{{ t('notFound.home') }}
        </Button>
      </template>
    </EmptyState>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import EmptyState from '../components/ui/EmptyState.vue'

const { t } = useI18n()
const router = useRouter()
</script>

<style scoped>
.not-found-panel {
  display: flex;
  justify-content: center;
  padding: 48px 24px;
}
</style>
