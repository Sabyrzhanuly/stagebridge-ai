<template>
  <PageHeader :title="pageTitle" :subtitle="pageSubtitle" />
  <Tabs v-model:value="tab" class="scenarios-hub">
    <TabList>
      <Tab value="restore"><i class="fa-solid fa-rotate" style="margin-right: 8px"></i>{{ t('scenariosHub.tabRestore') }}</Tab>
      <Tab value="structure"><i class="fa-solid fa-layer-group" style="margin-right: 8px"></i>{{ t('scenariosHub.tabStructure') }}</Tab>
    </TabList>
    <TabPanels>
      <TabPanel value="restore"><ScenariosView /></TabPanel>
      <TabPanel value="structure"><StructureSyncView /></TabPanel>
    </TabPanels>
  </Tabs>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import PageHeader from '../components/ui/PageHeader.vue'
import ScenariosView from './ScenariosView.vue'
import StructureSyncView from './StructureSyncView.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// Начальная вкладка из query (?tab=structure), чтобы глубокие ссылки на
// /structure-sync (редирект) открывали нужную вкладку.
const tab = ref(route.query.tab === 'structure' ? 'structure' : 'restore')

const pageTitle = computed(() =>
  tab.value === 'structure' ? t('scenariosHub.titleStructure') : t('scenariosHub.titleRestore'))
const pageSubtitle = computed(() =>
  tab.value === 'structure'
    ? t('scenariosHub.subtitleStructure')
    : t('scenariosHub.subtitleRestore'))

watch(tab, (v) => {
  router.replace({ path: '/scenarios', query: v === 'structure' ? { tab: 'structure' } : {} })
})
</script>

<style scoped>
/* Вложенные вью несут свой PageHeader/layout — убираем лишние отступы панелей. */
.scenarios-hub :deep(.p-tabpanels) {
  padding: 16px 0 0;
  background: transparent;
}
</style>
