<template>
  <div class="server-row-actions">
    <Button
      size="small"
      outlined
      v-tooltip.top="t('serverActions.overview')"
      :aria-label="t('serverActions.overviewAria')"
      @click="emit('open')"
    >
      <i class="fa-solid fa-circle-info" aria-hidden="true"></i>
    </Button>
    <Button
      size="small"
      outlined
      severity="secondary"
      v-tooltip.top="t('common.actions')"
      :aria-label="t('serverActions.actionsMenuAria')"
      aria-haspopup="true"
      @click="menu?.toggle($event)"
    >
      <i class="fa-solid fa-ellipsis" aria-hidden="true"></i>
    </Button>
    <Menu ref="menu" :model="menuItems" popup />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Menu from 'primevue/menu'

const { t } = useI18n()

const props = defineProps<{
  testing?: boolean
}>()

const emit = defineEmits<{
  open: []
  edit: []
  roles: []
  databases: []
  monitoring: []
  diagnostics: []
  test: []
  delete: []
}>()

const menu = ref<InstanceType<typeof Menu> | null>(null)

const menuItems = computed(() => [
  { label: t('common.edit'), icon: 'fa-solid fa-pen', command: () => emit('edit') },
  { separator: true },
  { label: t('serverActions.roles'), icon: 'fa-solid fa-users', command: () => emit('roles') },
  { label: t('serverActions.databases'), icon: 'fa-solid fa-database', command: () => emit('databases') },
  { label: t('serverActions.monitoring'), icon: 'fa-solid fa-chart-line', command: () => emit('monitoring') },
  { label: t('serverActions.diagnostics'), icon: 'fa-solid fa-stethoscope', command: () => emit('diagnostics') },
  { separator: true },
  {
    label: t('serverActions.testConnection'),
    icon: 'fa-solid fa-plug',
    disabled: props.testing,
    command: () => emit('test'),
  },
  {
    label: t('common.delete'),
    icon: 'fa-solid fa-trash',
    class: 'menu-item-danger',
    command: () => emit('delete'),
  },
])
</script>
