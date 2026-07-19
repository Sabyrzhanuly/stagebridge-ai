import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import Tooltip from 'primevue/tooltip'

import App from './App.vue'
import router from './router'
import { i18n } from './i18n'

import 'primeicons/primeicons.css'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './styles/design-tokens.css'
import './styles/global.css'
import './styles/scenarios.css'

const PgAdminPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '{sky.50}',
      100: '{sky.100}',
      200: '{sky.200}',
      300: '{sky.300}',
      400: '{sky.400}',
      500: '{sky.500}',
      600: '{sky.600}',
      700: '{sky.700}',
      800: '{sky.800}',
      900: '{sky.900}',
      950: '{sky.950}',
    },
  },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(PrimeVue, {
  theme: {
    preset: PgAdminPreset,
    options: {
      prefix: 'p',
      darkModeSelector: '.app-dark',
      cssLayer: false,
    },
  },
  // Модальные оверлеи (Dialog/ConfirmDialog) должны быть поверх полноэкранной
  // панели задач (.task-float.fullscreen: z-index 9999) — иначе confirm не виден.
  zIndex: {
    modal: 10100,
    overlay: 1000,
    menu: 1000,
    tooltip: 1100,
  },
})
app.use(ToastService)
app.use(ConfirmationService)
app.directive('tooltip', Tooltip)
app.mount('#app')
