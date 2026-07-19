<template>
  <div class="login-page app-dark">
    <div style="position: absolute; top: 20px; right: 20px; z-index: 2;"><LangSwitcher /></div>
    <div class="login-layout">
      <div class="login-hero">
        <div class="login-hero-badge">
          <i class="fa-solid fa-database" aria-hidden="true"></i>
          Real-Time Monitoring
        </div>
        <h2 class="login-hero-title">PG Control Center</h2>
        <p class="login-hero-desc">
          {{ t('login.heroDesc') }}
        </p>
        <ul class="login-features">
          <li>
            <i class="fa-solid fa-server" aria-hidden="true"></i>
            {{ t('login.feature1') }}
          </li>
          <li>
            <i class="fa-solid fa-box-archive" aria-hidden="true"></i>
            {{ t('login.feature2') }}
          </li>
          <li>
            <i class="fa-solid fa-chart-line" aria-hidden="true"></i>
            {{ t('login.feature3') }}
          </li>
        </ul>
      </div>

      <form class="login-card" @submit.prevent="handleLogin">
        <div class="login-brand">
          <img src="/logo_mini.png" alt="" class="login-brand-icon" aria-hidden="true" />
          <span class="login-brand-name">PG Control Center</span>
        </div>
        <h1 class="login-title">{{ t('login.title') }}</h1>
        <p class="login-subtitle">{{ t('login.subtitle') }}</p>

        <div class="flex-col form-stack">
          <div class="form-field">
            <label class="form-label" for="username">{{ t('login.username') }}</label>
            <InputText id="username" v-model="form.username" placeholder="admin" autofocus />
          </div>
          <div class="form-field">
            <label class="form-label" for="password">{{ t('login.password') }}</label>
            <Password id="password" v-model="form.password" :feedback="false" toggleMask fluid />
          </div>

          <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

          <Button type="submit" :loading="loading" :disabled="!form.username || !form.password" fluid>
            <i class="fa-solid fa-right-to-bracket btn-icon-left" aria-hidden="true"></i>
            {{ t('login.submit') }}
          </Button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import LangSwitcher from '../components/LangSwitcher.vue'
import Message from 'primevue/message'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!form.username || !form.password) return
  loading.value = true
  error.value = ''
  try {
    await authStore.login(form.username, form.password)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('login.authError')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.form-stack { gap: 14px; }
.login-footer-link {
  margin: 0;
  text-align: center;
  font-size: 13px;
  color: var(--text-color-secondary);
}
.login-footer-link a {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 600;
}
.login-footer-link a:hover { text-decoration: underline; }
</style>
