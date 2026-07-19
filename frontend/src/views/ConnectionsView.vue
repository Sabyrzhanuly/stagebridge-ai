<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('connections.title') }}</h1>
        <p>{{ t('connections.credentialNotice') }}</p>
      </div>
      <button class="primary-button" @click="startCreate">
        <Plus :size="18" />
        {{ t('connections.add') }}
      </button>
    </header>

    <div class="safety-banner" :class="store.externalHostsEnabled ? 'warning-banner' : ''">
      <ShieldCheck :size="18" />
      <span>{{ t('connections.externalHosts', { state: t(store.externalHostsEnabled ? 'common.enabled' : 'common.disabled') }) }}</span>
    </div>

    <section v-if="showForm" class="panel connection-form-panel">
      <div class="panel-header">
        <div>
          <h2>{{ t(editingId ? 'connections.editTitle' : 'connections.newTitle') }}</h2>
          <p>{{ t(editingId ? 'connections.keepPassword' : 'connections.credentialsBackend') }}</p>
        </div>
        <button class="icon-button" :title="t('accessibility.closeConnectionForm')" @click="closeForm"><X :size="18" /></button>
      </div>
      <form class="scenario-grid" novalidate @submit.prevent="save">
        <label>
          <span>{{ t('connections.name') }}</span>
          <input v-model.trim="form.name" required :placeholder="t('connections.namePlaceholder')" />
        </label>
        <label>
          <span>{{ t('connections.role') }}</span>
          <select v-model="form.role" required>
            <option value="production">{{ t('common.production') }}</option>
            <option value="development">{{ t('common.development') }}</option>
            <option value="staging">{{ t('common.staging') }}</option>
          </select>
        </label>
        <label class="wide-field">
          <span>{{ t('connections.host') }}</span>
          <input v-model.trim="form.host" required placeholder="postgres.example.com" />
        </label>
        <label>
          <span>{{ t('connections.port') }}</span>
          <input v-model.number="form.port" type="number" min="1" max="65535" required />
        </label>
        <label>
          <span>{{ t('connections.database') }}</span>
          <input v-model.trim="form.database" required placeholder="application" />
        </label>
        <label>
          <span>{{ t('connections.username') }}</span>
          <input v-model.trim="form.username" required autocomplete="username" />
        </label>
        <label>
          <span>{{ t('connections.password') }}</span>
          <input v-model="form.password" :required="!editingId" type="password" autocomplete="new-password" />
        </label>
        <label>
          <span>{{ t('connections.sslMode') }}</span>
          <select v-model="form.sslmode">
            <option value="disable">disable</option>
            <option value="allow">allow</option>
            <option value="prefer">prefer</option>
            <option value="require">require</option>
            <option value="verify-ca">verify-ca</option>
            <option value="verify-full">verify-full</option>
          </select>
        </label>
        <label>
          <span>{{ t('connections.statementTimeout') }}</span>
          <input v-model.number="form.statement_timeout" type="number" min="100" max="120000" required />
        </label>
        <label class="wide-field">
          <span>{{ t('connections.selectedSchemas') }}</span>
          <input v-model="schemasText" required placeholder="public, billing" />
        </label>

        <div class="wide-field probe-block">
          <button type="button" class="secondary-button" @click="probe" :disabled="probing || !form.host || !form.database || !form.username">
            <PlugZap :size="18" />{{ probing ? t('common.testing') : t('connections.testInForm') }}
          </button>
          <div v-if="probeResult" class="probe-result" :class="probeResult.ok ? 'ok' : 'fail'">
            <template v-if="probeResult.ok">
              <span class="probe-summary"><Database :size="15" /> {{ probeResult.database }} · PostgreSQL {{ probeResult.serverVersion }}</span>
              <div class="schema-chips">
                <span class="chip-label">{{ t('connections.availableSchemas') }}:</span>
                <label v-for="schema in probeResult.schemas" :key="schema" class="schema-chip">
                  <input type="checkbox" :checked="selectedSchemaList.includes(schema)" @change="toggleSchema(schema)" />{{ schema }}
                </label>
              </div>
            </template>
            <span v-else>{{ probeResult.message }}</span>
          </div>
        </div>

        <div class="form-actions wide-field">
          <button type="button" class="secondary-button" @click="closeForm">{{ t('common.cancel') }}</button>
          <button type="submit" class="primary-button" :disabled="saving">
            <Save :size="18" />
            {{ t(saving ? 'common.saving' : 'connections.save') }}
          </button>
        </div>
      </form>
      <p v-if="formError" class="error-line">{{ formError }}</p>
    </section>

    <section class="connection-grid">
      <article v-for="connection in store.connections" :key="connection.id" class="connection-card">
        <div class="connection-title">
          <Database :size="20" />
          <div>
            <strong>{{ connection.name }}</strong>
            <small>{{ connection.is_demo ? t('connections.demoData') : translateRole(connection.role) }}</small>
          </div>
          <StatusPill :label="statusLabel(connection)" />
        </div>
        <dl>
          <dt>{{ t('connections.database') }}</dt>
          <dd>{{ connection.database }}</dd>
          <dt>{{ t('connections.host') }}</dt>
          <dd>{{ connection.host }}:{{ connection.port }}</dd>
          <dt>{{ t('connections.role') }}</dt>
          <dd>{{ translateRole(connection.role) }}</dd>
          <dt>{{ t('connections.schemas') }}</dt>
          <dd>{{ connection.selected_schemas.join(', ') }}</dd>
          <dt>{{ t('connections.ssl') }}</dt>
          <dd>{{ connection.sslmode }}</dd>
        </dl>
        <div class="button-row">
          <button class="secondary-button" @click="test(connection)" :disabled="testingId === connection.id">
            <PlugZap :size="18" />
            {{ t(testingId === connection.id ? 'common.testing' : 'common.test') }}
          </button>
          <template v-if="!connection.is_demo">
            <button class="icon-button" :title="t('accessibility.editConnection')" @click="edit(connection)"><Pencil :size="17" /></button>
            <button class="icon-button danger-button" :title="t('accessibility.deleteConnection')" @click="remove(connection)"><Trash2 :size="17" /></button>
          </template>
        </div>
        <p v-if="results[String(connection.id)]" class="connection-result">{{ resultMessage(results[String(connection.id)]) }}</p>
        <p v-else-if="connection.last_test_message" class="connection-result">{{ savedTestMessage(connection) }}</p>
      </article>
      <div v-if="!store.connections.length" class="empty-state">{{ t('connections.empty') }}</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Database, Pencil, PlugZap, Plus, Save, ShieldCheck, Trash2, X } from '@lucide/vue'
import StatusPill from '../components/StatusPill.vue'
import { useStageBridgeStore } from '../stores/stagebridge'
import type { ConnectionInfo, ConnectionPayload, StatusLabel } from '../types'
import { translateRole } from '../i18n/formatters'

const store = useStageBridgeStore()
const { locale, t } = useI18n()
const results = reactive<Record<string, { ok: boolean; database?: string }>>({})
const showForm = ref(false)
const editingId = ref<number | null>(null)
const schemasText = ref('public')
const saving = ref(false)
const testingId = ref<number | string | null>(null)
const formError = ref('')
const probing = ref(false)
type ProbeResult = Awaited<ReturnType<typeof store.testAdhoc>>
const probeResult = ref<ProbeResult | null>(null)
const selectedSchemaList = computed(() => schemasText.value.split(',').map(s => s.trim()).filter(Boolean))

async function probe() {
  probing.value = true
  probeResult.value = null
  try {
    const result = await store.testAdhoc({
      host: form.host,
      port: form.port,
      database: form.database,
      username: form.username,
      password: form.password,
      sslmode: form.sslmode,
      statement_timeout: form.statement_timeout
    })
    probeResult.value = result
    if (result.ok && !schemasText.value.trim() && result.schemas?.length) {
      schemasText.value = result.schemas.join(', ')
    }
  } catch (error) {
    probeResult.value = { ok: false, message: error instanceof Error ? error.message : t('errors.requestFailed') }
  } finally {
    probing.value = false
  }
}

function toggleSchema(schema: string) {
  const list = selectedSchemaList.value
  const next = list.includes(schema) ? list.filter(item => item !== schema) : [...list, schema]
  schemasText.value = next.join(', ')
}

const emptyForm = (): ConnectionPayload => ({
  name: '',
  role: 'production',
  host: 'postgres',
  port: 5432,
  database: '',
  username: 'stagebridge',
  password: '',
  sslmode: 'prefer',
  selected_schemas: ['public'],
  statement_timeout: 5000
})
const form = reactive<ConnectionPayload>(emptyForm())

onMounted(() => store.fetchConnections())
watch(locale, () => {
  formError.value = ''
})

function startCreate() {
  Object.assign(form, emptyForm())
  schemasText.value = 'public'
  editingId.value = null
  formError.value = ''
  probeResult.value = null
  showForm.value = true
}

function edit(connection: ConnectionInfo) {
  if (typeof connection.id !== 'number') return
  Object.assign(form, {
    name: connection.name,
    role: connection.role,
    host: connection.host,
    port: connection.port,
    database: connection.database,
    username: connection.username,
    password: '',
    sslmode: connection.sslmode,
    selected_schemas: [...connection.selected_schemas],
    statement_timeout: connection.statement_timeout
  })
  schemasText.value = connection.selected_schemas.join(', ')
  editingId.value = connection.id
  formError.value = ''
  probeResult.value = null
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  formError.value = ''
  probeResult.value = null
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    const payload: ConnectionPayload = {
      ...form,
      selected_schemas: schemasText.value.split(',').map(value => value.trim()).filter(Boolean)
    }
    if (!payload.name || !payload.host || !payload.database || !payload.username) {
      formError.value = t('validation.required')
      return
    }
    if (!editingId.value && !payload.password) {
      formError.value = t('validation.passwordRequired')
      return
    }
    if (!payload.selected_schemas.length) {
      formError.value = t('validation.schemaRequired')
      return
    }
    if (payload.port < 1 || payload.port > 65535) {
      formError.value = t('validation.invalidPort')
      return
    }
    if (payload.statement_timeout < 100 || payload.statement_timeout > 120000) {
      formError.value = t('validation.timeoutRange')
      return
    }
    if (!payload.password) delete payload.password
    if (editingId.value) await store.updateConnection(editingId.value, payload)
    else await store.createConnection(payload)
    closeForm()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : t('errors.connectionSaveFailed')
  } finally {
    saving.value = false
  }
}

async function test(connection: ConnectionInfo) {
  testingId.value = connection.id
  try {
    const result = await store.testConnection(connection)
    results[String(connection.id)] = { ok: true, database: result.database }
  } catch {
    results[String(connection.id)] = { ok: false }
  } finally {
    testingId.value = null
  }
}

async function remove(connection: ConnectionInfo) {
  if (typeof connection.id !== 'number' || !window.confirm(t('connections.deleteConfirm', { name: connection.name }))) return
  await store.deleteConnection(connection.id)
}

function savedTestMessage(connection: ConnectionInfo): string {
  if (connection.is_demo) return t('connections.builtInSeeded')
  if (connection.last_test_status === 'connected') return t('connections.connected', { database: connection.database })
  if (connection.last_test_status === 'failed') return t('notifications.connectionFailed')
  return connection.last_test_message
}

function resultMessage(result: { ok: boolean; database?: string }): string {
  return result.ok ? t('connections.connected', { database: result.database || t('common.unknown') }) : t('notifications.connectionFailed')
}

function statusLabel(connection: ConnectionInfo): StatusLabel | string {
  if (connection.last_test_status === 'connected' || connection.is_demo) return 'Safe'
  if (connection.last_test_status === 'failed') return 'Blocking'
  return 'Untested'
}
</script>
