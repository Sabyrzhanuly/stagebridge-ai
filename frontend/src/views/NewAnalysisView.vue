<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('analysis.title') }}</h1>
        <p>{{ t('analysis.subtitle') }}</p>
      </div>
      <button class="secondary-button demo-button" @click="runDemo" :disabled="store.loading">
        <FlaskConical :size="18" />
        {{ t('analysis.runDemo') }}
      </button>
    </header>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2><span class="step-badge">1</span>{{ t('analysis.liveBanner') }}</h2>
          <p>{{ t('analysis.liveSafety') }}</p>
        </div>
      </div>
      <div class="scenario-grid">
        <label>
          <span>{{ t('analysis.productionProfile') }}</span>
          <select v-model.number="productionId" required>
            <option :value="0" disabled>{{ t('analysis.selectProduction') }}</option>
            <option v-for="profile in productionProfiles" :key="profile.id" :value="profile.id">{{ profile.name }} · {{ profile.database }}</option>
          </select>
        </label>
        <label>
          <span>{{ t('analysis.developmentProfile') }}</span>
          <select v-model.number="developmentId" required>
            <option :value="0" disabled>{{ t('analysis.selectDevelopment') }}</option>
            <option v-for="profile in developmentProfiles" :key="profile.id" :value="profile.id">{{ profile.name }} · {{ profile.database }}</option>
          </select>
        </label>

        <fieldset class="wide-field schema-selector">
          <legend>{{ t('analysis.schemasToCompare') }}</legend>
          <label v-for="schema in availableSchemas" :key="schema" class="checkbox-row">
            <input v-model="selectedSchemas" type="checkbox" :value="schema" />
            <span>{{ schema }}</span>
          </label>
          <span v-if="!availableSchemas.length" class="muted-line">{{ t('analysis.selectTestedProfiles') }}</span>
        </fieldset>

        <label class="wide-field">
          <span>{{ t('analysis.ignoredTables') }}</span>
          <textarea v-model="ignoredText" rows="3" placeholder="audit_log, archive.old_events"></textarea>
        </label>

        <label class="toggle-setting wide-field">
          <input v-model="runPreflight" type="checkbox" />
          <span>
            <strong>{{ t('analysis.runPreflight') }}</strong>
            <small>{{ t('analysis.preflightHint') }}</small>
          </span>
        </label>
      </div>
      <div class="form-actions">
        <RouterLink class="secondary-button" to="/connections"><Cable :size="18" />{{ t('analysis.manageConnections') }}</RouterLink>
        <button class="primary-button" @click="runLive" :disabled="store.loading || !canRunLive">
          <PlayCircle :size="18" />
          {{ t(store.loading ? 'analysis.analyzing' : 'analysis.runLive') }}
        </button>
      </div>
      <p v-if="store.error" class="error-line">{{ store.error }}</p>
    </section>

    <p class="hint-line"><FlaskConical :size="16" /> {{ t('analysis.demoHint') }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Cable, FlaskConical, PlayCircle } from '@lucide/vue'
import { useStageBridgeStore } from '../stores/stagebridge'

const store = useStageBridgeStore()
const router = useRouter()
const { locale, t } = useI18n()
const productionId = ref(0)
const developmentId = ref(0)
const selectedSchemas = ref<string[]>([])
const ignoredText = ref('')
const runPreflight = ref(true)

onMounted(() => store.fetchConnections())
watch(locale, () => {
  store.error = ''
})

const savedProfiles = computed(() => store.connections.filter(profile => !profile.is_demo && typeof profile.id === 'number'))
const productionProfiles = computed(() => savedProfiles.value.filter(profile => profile.role === 'production'))
const developmentProfiles = computed(() => savedProfiles.value.filter(profile => profile.role === 'development'))
const selectedProduction = computed(() => productionProfiles.value.find(profile => profile.id === productionId.value))
const selectedDevelopment = computed(() => developmentProfiles.value.find(profile => profile.id === developmentId.value))
const availableSchemas = computed(() => {
  const values = [...(selectedProduction.value?.selected_schemas || []), ...(selectedDevelopment.value?.selected_schemas || [])]
  return [...new Set(values)].sort()
})
const canRunLive = computed(() => productionId.value > 0 && developmentId.value > 0 && selectedSchemas.value.length > 0)

watch(availableSchemas, schemas => {
  selectedSchemas.value = selectedSchemas.value.filter(schema => schemas.includes(schema))
  if (!selectedSchemas.value.length) selectedSchemas.value = [...schemas]
})

async function runDemo() {
  const analysis = await store.runAnalysis({ mode: 'demo', schemas: ['public'], run_preflight: true })
  await router.push(`/analysis/${analysis.id}`)
}

async function runLive() {
  if (!canRunLive.value) return
  const ignored = ignoredText.value.split(/[,\n]/).map(value => value.trim()).filter(Boolean)
  const analysis = await store.runAnalysis({
    mode: 'live',
    production_profile_id: productionId.value,
    development_profile_id: developmentId.value,
    schemas: selectedSchemas.value,
    ignored_tables: ignored,
    run_preflight: runPreflight.value
  })
  await router.push(`/analysis/${analysis.id}`)
}
</script>
