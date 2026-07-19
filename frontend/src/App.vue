<template>
  <Toast position="top-right" />
  <ConfirmDialog />
  <template v-if="authStore.isAuthenticated && route.name !== 'login'">
    <AppLayout />
    <TaskPanel />
    <AiAssistant />
  </template>
  <template v-else>
    <router-view />
  </template>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import AppLayout from './components/AppLayout.vue'
import TaskPanel from './components/TaskPanel.vue'
import AiAssistant from './components/AiAssistant.vue'
import { useAuthStore } from './stores/auth'
import { useTasksStore } from './stores/tasks'
import { useThemeStore } from './stores/theme'
import { useHealthStore } from './stores/health'

const route = useRoute()
const authStore = useAuthStore()
const tasksStore = useTasksStore()
const healthStore = useHealthStore()
useThemeStore()

onMounted(() => {
  authStore.init()
  tasksStore.initTasks()
  // Статус worker теперь приходит пушем по WS (см. tasks.ts → worker_status);
  // здесь только локальный watchdog на «протухание», без сетевого поллинга.
  healthStore.startWatchdog()
})

onUnmounted(() => {
  tasksStore.disconnect()
  healthStore.stopWatchdog()
})
</script>
