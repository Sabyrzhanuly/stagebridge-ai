<template>
  <Button text severity="secondary" class="page-back-link" @click="router.push(to)">
    <i class="fa-solid fa-arrow-left" aria-hidden="true"></i>
    {{ label ?? t('common.back') }}
  </Button>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter, type RouteLocationRaw } from 'vue-router'
import Button from 'primevue/button'

defineProps<{
  to: RouteLocationRaw
  label?: string
}>()

const { t } = useI18n()
const router = useRouter()
</script>
