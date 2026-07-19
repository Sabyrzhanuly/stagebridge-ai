<template>
  <section class="topology">
    <div class="node prod">
      <Database :size="22" />
      <span>{{ t('common.production') }}</span>
      <small>{{ t('topology.readOnly') }}</small>
    </div>
    <ArrowRight :size="20" />
    <div class="node dev">
      <GitCompare :size="22" />
      <span>{{ t('common.development') }}</span>
      <small>{{ t('topology.schemaSource') }}</small>
    </div>
    <ArrowRight :size="20" />
    <div class="node dry">
      <ShieldCheck :size="22" />
      <span>{{ t('analysis.dryRun') }}</span>
      <small>{{ t('topology.isolated') }}</small>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ArrowRight, Database, GitCompare, ShieldCheck } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
