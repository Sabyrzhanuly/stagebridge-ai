<template>
  <Dialog
    :visible="visible"
    modal
    :header="mode === 'create' ? t('serverForm.titleCreate') : t('serverForm.titleEdit')"
    :style="{ width: '520px' }"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="flex-col form-stack">
      <div v-if="showOrgPicker" class="form-field">
        <label class="form-label" for="srv-org">{{ t('serverForm.organization') }}</label>
        <Select
          id="srv-org"
          v-model="form.organization_id"
          :options="orgOptions"
          option-label="name"
          option-value="id"
          :placeholder="t('serverForm.selectOrg')"
          filter
          fluid
        />
        <small v-if="mode === 'edit' && !form.organization_id" class="field-hint field-hint-warn">
          {{ t('serverForm.noOrgHint') }}
        </small>
      </div>
      <div class="form-field">
        <label class="form-label" for="srv-name">{{ t('common.name') }}</label>
        <InputText id="srv-name" v-model="form.name" fluid />
      </div>
      <div class="flex-row" style="gap: 12px">
        <div class="form-field" style="flex: 2">
          <label class="form-label" for="srv-host">{{ t('serverForm.host') }}</label>
          <InputText id="srv-host" v-model="form.host" fluid />
        </div>
        <div class="form-field" style="flex: 1">
          <label class="form-label" for="srv-port">{{ t('serverForm.port') }}</label>
          <InputNumber id="srv-port" v-model="form.port" :use-grouping="false" fluid />
        </div>
      </div>
      <div class="form-field">
        <label class="form-label" for="srv-user">Admin User</label>
        <InputText id="srv-user" v-model="form.admin_user" fluid />
      </div>
      <div class="form-field">
        <label class="form-label" for="srv-pass">
          {{ mode === 'create' ? t('serverForm.password') : t('serverForm.newPassword') }}
        </label>
        <Password
          id="srv-pass"
          v-model="form.admin_password"
          :feedback="false"
          toggleMask
          fluid
          :placeholder="mode === 'edit' ? t('serverForm.passwordEditHint') : ''"
        />
      </div>
      <div class="form-field">
        <label class="form-label" for="srv-env">{{ t('serverForm.environment') }}</label>
        <Select
          id="srv-env"
          v-model="form.environment"
          :options="envOptions"
          option-label="label"
          option-value="value"
          fluid
        />
      </div>
      <div v-if="mode === 'edit'" class="form-field form-field-inline">
        <label class="form-label" for="srv-active">{{ t('serverForm.active') }}</label>
        <ToggleSwitch id="srv-active" v-model="form.is_active" />
      </div>
    </div>
    <template #footer>
      <Button text @click="emit('update:visible', false)">{{ t('common.cancel') }}</Button>
      <Button :loading="saving" :disabled="!canSubmit" @click="submit">
        <i class="fa-solid fa-check btn-icon-left" aria-hidden="true"></i>
        {{ mode === 'create' ? t('serverForm.create') : t('common.save') }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { reactive, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Password from 'primevue/password'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import type { Server } from '../../api/types'

const { t } = useI18n()

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  server?: Server | null
  orgOptions: { id: number; name: string }[]
  showOrgPicker: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [payload: Record<string, unknown>]
}>()

const envOptions = [
  { label: 'dev', value: 'dev' },
  { label: 'test', value: 'test' },
  { label: 'staging', value: 'staging' },
  { label: 'production', value: 'production' },
]

const emptyForm = () => ({
  organization_id: null as number | null,
  name: '',
  host: '',
  port: 5432,
  admin_user: 'postgres',
  admin_password: '',
  environment: 'dev',
  is_active: true,
})

const form = reactive(emptyForm())

watch(
  () => [props.visible, props.mode, props.server] as const,
  ([visible, mode, server]) => {
    if (!visible) return
    Object.assign(form, emptyForm())
    if (mode === 'edit' && server) {
      form.organization_id = server.organization_id
      form.name = server.name
      form.host = server.host
      form.port = server.port
      form.admin_user = server.admin_user
      form.environment = server.environment
      form.is_active = server.is_active
    }
  },
  { immediate: true },
)

const canSubmit = computed(() => {
  if (!form.name.trim() || !form.host.trim()) return false
  if (props.showOrgPicker && !form.organization_id) return false
  if (props.mode === 'create' && !form.admin_password) return false
  return true
})

function submit() {
  const payload: Record<string, unknown> = {
    name: form.name.trim(),
    host: form.host.trim(),
    port: form.port,
    admin_user: form.admin_user.trim(),
    environment: form.environment,
  }
  if (props.showOrgPicker && form.organization_id) {
    payload.organization_id = form.organization_id
  }
  if (form.admin_password) payload.admin_password = form.admin_password
  if (props.mode === 'edit') payload.is_active = form.is_active
  emit('submit', payload)
}
</script>

<style scoped>
.form-stack { gap: 14px; }
.btn-icon-left { margin-right: 8px; }
.form-field-inline {
  display: flex;
  align-items: center;
  gap: 12px;
}
.field-hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.field-hint-warn { color: #b45309; }
</style>
