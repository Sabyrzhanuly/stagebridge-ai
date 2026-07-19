<template>
  <PageHeader :title="t('settings.pageTitle')" :subtitle="t('settings.pageSubtitle')" />

  <div class="card-panel card-panel--flush">
    <Tabs v-model:value="settingsTab">
      <TabList>
        <Tab value="minio"><i class="fa-solid fa-cloud" style="margin-right: 8px"></i>{{ t('settings.tabStorage') }}</Tab>
        <Tab value="channels"><i class="fa-solid fa-bell" style="margin-right: 8px"></i>{{ t('settings.tabChannels') }}</Tab>
        <Tab value="rules"><i class="fa-solid fa-bolt" style="margin-right: 8px"></i>{{ t('settings.tabRules') }}</Tab>
        <Tab value="schedules"><i class="fa-solid fa-calendar-days" style="margin-right: 8px"></i>{{ t('settings.tabSchedules') }}</Tab>
        <Tab v-if="auth.isSuperAdmin" value="pg-versions"><i class="fa-solid fa-cubes" style="margin-right: 8px"></i>{{ t('settings.tabPgClients') }}</Tab>
        <Tab v-if="auth.isSuperAdmin" value="ai"><i class="fa-solid fa-wand-magic-sparkles" style="margin-right: 8px"></i>{{ t('settings.ai.tab') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="minio">
          <div class="flex-row tab-panel-toolbar">
            <Button @click="openStorageModal()">
              <i class="fa-solid fa-plus" style="margin-right: 6px"></i>{{ t('settings.addStorage') }}
            </Button>
          </div>

          <DataTable :value="s3Storages" striped-rows :loading="s3StoragesLoading">
            <Column field="name" :header="t('common.name')" />
            <Column field="endpoint" header="Endpoint" />
            <Column field="bucket" header="Bucket" style="width: 140px" />
            <Column header="Region" style="width: 110px">
              <template #body="{ data }">
                <span class="settings-muted">{{ data.region || '—' }}</span>
              </template>
            </Column>
            <Column header="API" style="width: 58px">
              <template #body="{ data }">
                <Tag :value="data.api_type === 'swift' ? 'Swift' : 'S3'" severity="secondary" />
              </template>
            </Column>
            <Column header="Sig" style="width: 52px">
              <template #body="{ data }">
                <span v-if="data.api_type === 'swift'" class="settings-muted">—</span>
                <Tag v-else :value="data.sign_version === 'v2' ? 'V2' : 'V4'" severity="secondary" />
              </template>
            </Column>
            <Column header="TLS" style="width: 70px">
              <template #body="{ data }">
                <Tag :value="data.secure ? 'HTTPS' : 'HTTP'" :severity="data.secure ? 'success' : 'secondary'" />
              </template>
            </Column>
            <Column header="" style="width: 150px">
              <template #body="{ data }">
                <div class="flex-row" style="gap: 6px">
                  <Button size="small" outlined severity="secondary" :loading="s3TestingId === data.id" @click="testSavedStorage(data.id)">
                    <i class="fa-solid fa-plug"></i>
                  </Button>
                  <Button size="small" text severity="secondary" @click="openStorageModal(data)">
                    <i class="fa-solid fa-pen-to-square"></i>
                  </Button>
                  <Button size="small" text severity="danger" :loading="s3DeletingId === data.id" @click="deleteStorage(data.id)">
                    <i class="fa-solid fa-trash"></i>
                  </Button>
                </div>
              </template>
            </Column>
            <template #empty>
              <div class="pg-versions-empty">
                <i class="fa-solid fa-cloud"></i>
                {{ t('settings.storageEmpty') }}
              </div>
            </template>
          </DataTable>

          <div class="s3-servers-section">
            <div class="s3-servers-title">{{ t('settings.serverBindingTitle') }}</div>
            <div class="s3-servers-hint">
              {{ t('settings.serverBindingHint') }}
            </div>
            <DataTable :value="servers" striped-rows>
              <Column field="name" :header="t('common.server')" />
              <Column :header="t('settings.storageS3Column')">
                <template #body="{ data }">
                  <Select
                    :model-value="data.storage_id"
                    :options="storageAssignOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('settings.notSelected')"
                    show-clear
                    style="min-width: 220px"
                    :loading="serverStorageSaving === data.id"
                    @update:model-value="(v) => assignServerStorage(data.id, v)"
                  />
                </template>
              </Column>
            </DataTable>
          </div>
        </TabPanel>

        <TabPanel value="channels">
          <div class="flex-row tab-panel-toolbar">
            <Button @click="openChannelModal()">
              <i class="fa-solid fa-plus" style="margin-right: 6px"></i>{{ t('settings.addChannel') }}
            </Button>
          </div>
          <DataTable :value="channels" striped-rows>
            <Column field="name" :header="t('common.name')" />
            <Column field="channel_type" :header="t('settings.type')" style="width: 110px">
              <template #body="{ data }">
                <Tag :value="data.channel_type" severity="info" />
              </template>
            </Column>
            <Column field="is_active" :header="t('settings.active')" style="width: 90px">
              <template #body="{ data }">
                <ToggleSwitch
                  :model-value="data.is_active"
                  @update:model-value="(v) => toggleChannel(data.id, v)"
                />
              </template>
            </Column>
            <Column header="" style="width: 210px">
              <template #body="{ data }">
                <div class="flex-row" style="gap: 6px">
                  <Button
                    size="small" text severity="secondary"
                    @click="showChannelHistory(data)"
                    :title="t('settings.sendLogTitle')"
                  >
                    <i class="fa-solid fa-clock-rotate-left"></i>
                  </Button>
                  <Button
                    size="small" outlined severity="secondary"
                    :loading="testingChannelId === data.id"
                    @click="testChannel(data.id)"
                    :title="t('settings.sendTestMessage')"
                  >
                    <i class="fa-solid fa-paper-plane"></i>
                  </Button>
                  <Button size="small" text severity="secondary" @click="openChannelModal(data)" :title="t('common.edit')">
                    <i class="fa-solid fa-pen-to-square"></i>
                  </Button>
                  <Button size="small" severity="danger" text @click="deleteChannel(data.id)" :title="t('common.delete')">
                    <i class="fa-solid fa-trash"></i>
                  </Button>
                </div>
              </template>
            </Column>
          </DataTable>
        </TabPanel>

        <TabPanel value="rules">
          <div class="flex-row tab-panel-toolbar">
            <Button @click="openRuleModal">
              <i class="fa-solid fa-plus" style="margin-right: 6px"></i>{{ t('settings.addRule') }}
            </Button>
            <span style="font-size: 12px; color: var(--p-text-muted-color)">
              {{ t('settings.rulesCount', { count: rules.length }) }}
            </span>
          </div>
          <DataTable :value="rules" striped-rows>
            <Column :header="t('settings.category')" style="width: 140px">
              <template #body="{ data }">
                <Tag
                  :value="ruleCategory(data.rule_type).label"
                  :severity="ruleCategory(data.rule_type).severity"
                  style="font-size: 11px"
                />
              </template>
            </Column>
            <Column field="name" :header="t('common.name')" />
            <Column :header="t('settings.event')" style="width: 200px">
              <template #body="{ data }">
                {{ ruleTypeLabel(data.rule_type) }}
              </template>
            </Column>
            <Column :header="t('settings.channel')" style="width: 160px">
              <template #body="{ data }">
                <span v-if="data.channel_name">
                  <i class="fa-solid fa-bell" style="margin-right: 5px; color: var(--p-text-muted-color)"></i>
                  {{ data.channel_name }}
                </span>
                <span v-else style="color: var(--p-text-muted-color); font-size: 12px">#{{ data.channel_id }}</span>
              </template>
            </Column>
            <Column :header="t('common.server')" style="width: 160px">
              <template #body="{ data }">
                <span v-if="data.server_name">
                  <i class="fa-solid fa-server" style="margin-right: 5px; color: var(--p-text-muted-color)"></i>
                  {{ data.server_name }}
                </span>
                <Tag v-else :value="t('settings.allServers')" severity="secondary" style="font-size: 11px" />
              </template>
            </Column>
            <Column :header="t('settings.activeNeuter')" style="width: 90px">
              <template #body="{ data }">
                <ToggleSwitch
                  :model-value="data.is_active"
                  @update:model-value="(v) => toggleRule(data.id, v)"
                />
              </template>
            </Column>
            <Column style="width: 90px">
              <template #body="{ data }">
                <div class="flex-row" style="gap: 4px">
                  <Button size="small" text severity="secondary" @click="openRuleModal(data)" :title="t('common.edit')">
                    <i class="fa-solid fa-pen-to-square"></i>
                  </Button>
                  <Button size="small" severity="danger" text @click="deleteRule(data.id)" :title="t('common.delete')">
                    <i class="fa-solid fa-trash"></i>
                  </Button>
                </div>
              </template>
            </Column>
          </DataTable>
        </TabPanel>

        <TabPanel value="schedules">
          <div class="flex-row tab-panel-toolbar">
            <Button @click="openScheduleModal()">
              <i class="fa-solid fa-plus" style="margin-right: 6px"></i>{{ t('settings.addSchedule') }}
            </Button>
            <span style="font-size: 12px; color: var(--p-text-muted-color)">
              {{ t('settings.builtinSchedulesHint') }}
            </span>
          </div>
          <DataTable :value="cronSchedules" striped-rows>
            <Column field="name" :header="t('common.name')" />
            <Column field="cron_expression" header="Cron" style="width: 160px">
              <template #body="{ data }">
                <code class="code-chip">{{ data.cron_expression }}</code>
              </template>
            </Column>
            <Column field="description" :header="t('settings.description')" />
            <Column header="" style="width: 90px">
              <template #body="{ data }">
                <div class="flex-row" style="gap: 4px">
                  <Tag v-if="data.is_builtin" :value="t('settings.builtin')" severity="secondary" style="font-size: 10px" />
                  <template v-else>
                    <Button size="small" text severity="secondary" @click="openScheduleModal(data)" :title="t('common.edit')">
                      <i class="fa-solid fa-pen-to-square"></i>
                    </Button>
                    <Button size="small" text severity="danger" @click="deleteSchedule(data.id)" :title="t('common.delete')">
                      <i class="fa-solid fa-trash"></i>
                    </Button>
                  </template>
                </div>
              </template>
            </Column>
          </DataTable>
        </TabPanel>

        <TabPanel v-if="auth.isSuperAdmin" value="pg-versions">
          <div class="tab-panel-toolbar tab-panel-toolbar--stacked">
            <div style="font-size: 13px; color: var(--p-text-muted-color); margin-bottom: 10px" v-html="t('settings.pgClientsIntro')"></div>
            <div class="flex-row" style="gap: 10px; flex-wrap: wrap; align-items: center">
              <Select
                v-model="newPgMajor"
                :options="catalogAddOptions"
                option-label="label"
                option-value="value"
                :placeholder="t('settings.selectFromPgdg')"
                filter
                style="min-width: 280px"
              />
              <Button size="small" :disabled="!newPgMajor" :loading="pgCatalogAdding" @click="addPgClientToCatalog">
                <i class="fa-solid fa-plus" style="margin-right: 5px"></i>{{ t('common.add') }}
              </Button>
              <Button
                outlined
                size="small"
                :loading="pgRepoRefreshRunning || pgRefreshSending"
                :disabled="pgRepoRefreshRunning || pgRefreshSending"
                @click="submitPgRefresh(refreshAvailableFromRepo)"
              >
                <i class="fa-solid fa-cloud-arrow-down" style="margin-right: 5px"></i>{{ t('settings.loadFromPgdg') }}
              </Button>
            </div>
            <div v-if="availablePgPackages.length" class="pg-repo-hint">
              {{ t('settings.inRepoCount', { count: availablePgPackages.length }) }}
            </div>
            <div v-else-if="!pgRepoRefreshRunning" class="pg-repo-hint pg-repo-hint--muted">
              {{ t('settings.pgdgEmpty') }}
            </div>
          </div>

          <DataTable :value="pgVersions" striped-rows :loading="pgVersionsLoading">
            <Column field="major" :header="t('settings.version')" style="width: 110px">
              <template #body="{ data }">
                <span class="pg-version-num">PG {{ data.major }}</span>
              </template>
            </Column>
            <Column :header="t('settings.source')" style="width: 130px">
              <template #body="{ data }">
                <Tag
                  :value="pgClientSourceLabel(data.source)"
                  :severity="data.source === 'requested' ? 'warn' : 'secondary'"
                />
              </template>
            </Column>
            <Column :header="t('common.status')" style="width: 170px">
              <template #body="{ data }">
                <span class="pg-version-status" :class="data.installed ? 'status-ok' : 'status-missing'">
                  <i :class="data.installed ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark'"></i>
                  {{ data.installed ? t('settings.installed') : t('settings.notInstalled') }}
                </span>
              </template>
            </Column>
            <Column header="PGDG" style="width: 180px">
              <template #body="{ data }">
                <span v-if="data.available_in_repo && data.candidate" class="text-mono" style="font-size: 12px">
                  {{ data.candidate }}
                </span>
                <Tag v-else-if="!data.available_in_repo" severity="danger" :value="t('settings.notInPgdg')" />
                <span v-else class="text-muted">—</span>
              </template>
            </Column>
            <Column :header="t('settings.servers')">
              <template #body="{ data }">
                <span v-if="!data.servers?.length" class="text-muted">—</span>
                <span v-else class="pg-version-servers">
                  <span
                    v-for="s in data.servers"
                    :key="s.id"
                    class="pg-version-server-chip"
                  >{{ s.name }}</span>
                </span>
              </template>
            </Column>
            <Column :header="t('common.actions')" style="width: 260px">
              <template #body="{ data }">
                <div
                  v-if="tasksStore.findPgClientTask(data.major)"
                  class="flex-row running-cell"
                  style="cursor: pointer"
                  @click="tasksStore.focusTask(tasksStore.findPgClientTask(data.major)!.taskId)"
                >
                  <i class="fa-solid fa-spinner fa-spin running-icon"></i>
                  <span class="running-text">
                    {{ tasksStore.PG_CLIENT_STAGE_LABELS[tasksStore.findPgClientTask(data.major)!.stage] || tasksStore.findPgClientTask(data.major)!.stage }}
                  </span>
                  <span class="running-pct">
                    {{ tasksStore.progressPercent(tasksStore.findPgClientTask(data.major)!) }}%
                  </span>
                </div>
                <div v-else class="flex-row" style="gap: 6px; flex-wrap: wrap">
                  <Button
                    v-if="!data.installed"
                    size="small"
                    :loading="pgInstallMajor === data.major"
                    @click="installPgClient(data.major)"
                  >
                    {{ t('settings.install') }}
                  </Button>
                  <Button
                    v-else
                    size="small"
                    outlined
                    severity="danger"
                    :disabled="data.requested"
                    :loading="pgUninstallMajor === data.major"
                    @click="uninstallPgClient(data.major)"
                  >
                    {{ t('settings.uninstallClient') }}
                  </Button>
                  <Button
                    size="small"
                    text
                    severity="secondary"
                    :disabled="data.requested"
                    :loading="pgCatalogRemoving === data.major"
                    @click="removePgClientFromCatalog(data.major)"
                  >
                    {{ t('settings.remove') }}
                  </Button>
                </div>
              </template>
            </Column>
            <template #empty>
              <div class="pg-versions-empty">
                <i class="fa-solid fa-circle-info"></i>
                {{ t('settings.pgVersionsEmpty') }}
              </div>
            </template>
          </DataTable>
        </TabPanel>

        <TabPanel v-if="auth.isSuperAdmin" value="ai">
          <div class="card-panel">
            <div class="card-panel-title">
              <span><i class="fa-solid fa-wand-magic-sparkles" style="margin-right: 8px"></i>{{ t('settings.ai.title') }}</span>
              <Tag :severity="aiConfig.configured ? 'success' : 'secondary'" :value="aiConfig.configured ? t('settings.ai.enabled') : t('settings.ai.disabled')" />
            </div>
            <p class="muted" style="margin: 4px 0 18px">{{ t('settings.ai.hint') }}</p>
            <div class="ai-settings-form">
              <label class="ai-settings-field">
                <span>OpenAI API Key</span>
                <input
                  v-model="aiKeyInput"
                  type="password"
                  autocomplete="off"
                  :placeholder="aiConfig.configured ? t('settings.ai.keyPlaceholder') : 'sk-...'"
                  class="ai-settings-input"
                />
              </label>
              <label class="ai-settings-field">
                <span>{{ t('settings.ai.model') }}</span>
                <input v-model="aiModelInput" type="text" placeholder="gpt-5.6" class="ai-settings-input" />
              </label>
              <div class="flex-row" style="gap: 10px">
                <Button :loading="aiSaving" @click="saveAiConfig">
                  <i class="fa-solid fa-floppy-disk btn-icon-left"></i>{{ t('settings.ai.save') }}
                </Button>
                <Button v-if="aiConfig.configured" outlined severity="danger" @click="clearAiKey">
                  <i class="fa-solid fa-trash btn-icon-left"></i>{{ t('settings.ai.clearKey') }}
                </Button>
              </div>
              <p v-if="aiConfig.configured" class="muted" style="margin-top: 4px">
                {{ t('settings.ai.activeModel') }} <strong>{{ aiConfig.model }}</strong> · {{ t('settings.ai.source', { source: aiConfig.source === 'db' ? t('settings.ai.sourceDb') : t('settings.ai.sourceEnv') }) }}
              </p>
            </div>
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>

  <Dialog
    v-model:visible="showChannelHistoryModal"
    modal
    :header="t('settings.logHeader', { name: channelHistoryName })"
    :style="{ width: 'min(1040px, 96vw)' }"
    class="channel-history-dialog"
  >
    <div class="channel-history-layout">
      <div class="flex-row channel-history-toolbar">
        <Select
          v-model="channelHistoryServerId"
          :options="[{ id: null, name: t('settings.allServers') }, ...servers]"
          option-label="name"
          option-value="id"
          :placeholder="t('settings.filterByServer')"
          style="width: 220px"
          @change="fetchChannelHistory"
        />
        <Button outlined size="small" :loading="channelHistoryLoading" @click="fetchChannelHistory">
          <i class="fa-solid fa-rotate-right" style="margin-right: 5px"></i>{{ t('common.refresh') }}
        </Button>
      </div>

      <DataTable
        class="app-data-table channel-history-table"
        :value="channelHistory"
        v-model:selection="selectedNotif"
        selectionMode="single"
        dataKey="id"
        :metaKeySelection="false"
        :loading="channelHistoryLoading"
        striped-rows
        size="small"
        scrollable
        scrollHeight="320px"
        :rowClass="notifRowClass"
      >
        <template #empty>
          <EmptyState
            icon="fa-solid fa-bell-slash"
            :title="t('settings.noSends')"
            :description="t('settings.noSendsDesc')"
            compact
          />
        </template>
        <Column field="status" :header="t('common.status')" style="width: 108px">
          <template #body="{ data }">
            <Tag
              :severity="data.status === 'sent' ? 'success' : 'danger'"
              :value="data.status === 'sent' ? t('settings.sent') : t('settings.error')"
            />
          </template>
        </Column>
        <Column :header="t('settings.rule')" style="width: 160px">
          <template #body="{ data }">
            <span v-if="data.rule_name" class="channel-history-clip">{{ data.rule_name }}</span>
            <Tag v-else :value="t('settings.manual')" severity="secondary" style="font-size: 11px" />
          </template>
        </Column>
        <Column :header="t('common.server')" style="width: 140px">
          <template #body="{ data }">
            <span v-if="data.server_name" class="channel-history-clip">{{ data.server_name }}</span>
            <span v-else class="settings-muted">—</span>
          </template>
        </Column>
        <Column field="sent_at" :header="t('settings.time')" style="width: 148px">
          <template #body="{ data }">{{ formatDate(data.sent_at) }}</template>
        </Column>
        <Column :header="t('settings.message')" style="width: 120px">
          <template #body="{ data }">
            <span class="channel-history-clip">{{ notifPreview(data.message) }}</span>
          </template>
        </Column>
      </DataTable>

      <div v-if="selectedNotif" class="channel-history-detail">
        <div class="channel-history-detail-head">
          <span class="channel-history-detail-title">
            {{ formatDate(selectedNotif.sent_at) }}
            · {{ selectedNotif.status === 'sent' ? t('settings.sent') : t('settings.error') }}
            <template v-if="selectedNotif.rule_name"> · {{ selectedNotif.rule_name }}</template>
          </span>
          <Button text size="small" severity="secondary" @click="copyNotifMessage">
            <i class="fa-solid fa-copy" style="margin-right: 5px"></i>{{ t('settings.copy') }}
          </Button>
        </div>
        <pre class="channel-history-message">{{ stripHtml(selectedNotif.message) }}</pre>
      </div>
      <p v-else-if="channelHistory.length" class="channel-history-hint settings-muted">
        {{ t('settings.selectRowHint') }}
      </p>
    </div>
  </Dialog>

  <Dialog v-model:visible="showStorageModal" modal :header="editingStorageId ? t('settings.editStorage') : t('settings.addStorage')" :style="{ width: '520px' }">
    <div class="flex-col" style="gap: 14px">
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('common.name') }}</label>
        <InputText v-model="storageForm.name" :placeholder="t('settings.storageNamePlaceholder')" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">API</label>
        <Select
          v-model="storageForm.api_type"
          :options="apiTypeOptions"
          option-label="label"
          option-value="value"
        />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ storageForm.api_type === 'swift' ? 'Auth URL' : 'Endpoint' }} <span class="settings-hint">{{ t('settings.hostPortHint') }}</span></label>
        <InputText v-model="storageForm.endpoint" :placeholder="storageForm.api_type === 'swift' ? 'https://storage.example.com' : 's3.example.com:443'" />
      </div>
      <template v-if="storageForm.api_type === 's3'">
        <div class="flex-col" style="gap: 4px">
          <label class="settings-label">Region <span class="settings-hint">{{ t('settings.optional') }}</span></label>
          <InputText v-model="storageForm.region" placeholder="" />
        </div>
        <div class="flex-col" style="gap: 4px">
          <label class="settings-label">{{ t('settings.signRequests') }}</label>
          <Select
            v-model="storageForm.sign_version"
            :options="signVersionOptions"
            option-label="label"
            option-value="value"
          />
          <small class="settings-muted" style="font-size: 11px">
            {{ t('settings.signVersionHint') }}
          </small>
        </div>
      </template>
      <template v-else>
        <div class="flex-row" style="gap: 12px">
          <div class="flex-col" style="gap: 4px; flex: 1">
            <label class="settings-label">Project <span class="settings-hint">{{ t('settings.optional') }}</span></label>
            <InputText v-model="storageForm.swift_project" placeholder="" />
          </div>
          <div class="flex-col" style="gap: 4px; flex: 1">
            <label class="settings-label">Domain <span class="settings-hint">{{ t('settings.defaultDefault') }}</span></label>
            <InputText v-model="storageForm.swift_domain" placeholder="default" />
          </div>
        </div>
        <small class="settings-muted" style="font-size: 11px">
          {{ t('settings.swiftUsernameHint') }}
        </small>
      </template>
      <div class="flex-row" style="gap: 12px">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="settings-label">{{ storageForm.api_type === 'swift' ? 'Username' : 'Access Key' }}</label>
          <InputText v-model="storageForm.access_key" />
        </div>
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="settings-label">{{ storageForm.api_type === 'swift' ? 'Password' : 'Secret Key' }}</label>
          <InputText v-model="storageForm.secret_key" type="password" />
        </div>
      </div>
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ storageForm.api_type === 'swift' ? 'Container' : 'Bucket' }}</label>
        <InputText v-model="storageForm.bucket" placeholder="pg-backups" />
      </div>
      <div class="flex-row" style="gap: 10px; align-items: center">
        <ToggleSwitch v-model="storageForm.secure" input-id="storage-secure" />
        <label for="storage-secure" style="cursor: pointer; font-size: 13px">HTTPS (TLS)</label>
      </div>
      <div v-if="storageTestResult" class="minio-test-result" :class="storageTestResult.ok ? 'ok' : 'fail'">
        <i :class="storageTestResult.ok ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark'"></i>
        {{ storageTestResult.message }}
      </div>
    </div>
    <template #footer>
      <Button text @click="showStorageModal = false">{{ t('common.cancel') }}</Button>
      <Button outlined :loading="storageTesting" @click="testStorageForm">{{ t('common.test') }}</Button>
      <Button :loading="storageSaving" @click="saveStorage">{{ editingStorageId ? t('common.save') : t('settings.create') }}</Button>
    </template>
  </Dialog>

  <Dialog v-model:visible="showChannelModal" modal :header="editingChannelId ? t('settings.editChannel') : t('settings.addChannel')" :style="{ width: '560px' }">
    <div class="flex-col" style="gap: 14px">
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('common.name') }}</label>
        <InputText v-model="channelForm.name" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('settings.type') }}</label>
        <Select v-model="channelForm.channel_type" :options="typeOptions" option-label="label" option-value="value" />
      </div>
      <template v-if="channelForm.channel_type === 'telegram'">
        <div class="flex-col" style="gap: 4px">
          <label>Bot Token</label>
          <InputText v-model="channelForm.bot_token" placeholder="1234567890:AAF..." />
        </div>
        <div class="flex-col" style="gap: 4px">
          <label>Chat ID</label>
          <div class="flex-row" style="gap: 6px; align-items: center">
            <InputText v-model="channelForm.chat_id" placeholder="-100123456789" style="flex: 1" />
            <Button
              outlined
              size="small"
              :loading="chatIdLoading"
              :disabled="!channelForm.bot_token"
              @click="fetchChatIds"
              :title="t('settings.getChatIdTitle')"
            >
              <i class="fa-brands fa-telegram" style="margin-right: 5px"></i>{{ t('settings.find') }}
            </Button>
          </div>
          <small style="color: var(--p-text-muted-color); font-size: 11px">
            {{ t('settings.chatIdHint') }}
          </small>
        </div>
        <!-- Найденные чаты -->
        <div v-if="foundChats.length > 0" class="found-chats">
          <div style="font-size: 12px; font-weight: 600; margin-bottom: 6px; color: var(--p-text-muted-color)">
            {{ t('settings.foundChatsLabel') }}
          </div>
          <div
            v-for="c in foundChats"
            :key="c.id"
            class="found-chat-item"
            :class="{ selected: channelForm.chat_id === String(c.id) }"
            @click="channelForm.chat_id = String(c.id)"
          >
            <i :class="c.type === 'private' ? 'fa-solid fa-user' : 'fa-solid fa-users'" style="width:14px"></i>
            <span class="found-chat-name">{{ c.name }}</span>
            <code class="found-chat-id">{{ c.id }}</code>
          </div>
        </div>
        <div v-else-if="chatIdSearched && !chatIdLoading" class="found-chats-empty">
          <i class="fa-solid fa-circle-info"></i>
          {{ t('settings.noMessagesFound') }}
        </div>
      </template>
      <template v-else>
        <div class="flex-col" style="gap: 4px">
          <label>{{ t('settings.emailRecipient') }}</label>
          <InputText v-model="channelForm.email_to" placeholder="alerts@company.ru" />
          <small style="color: var(--p-text-muted-color); font-size: 11px">
            {{ t('settings.emailToHint') }}
          </small>
        </div>
        <div class="channel-smtp-grid">
          <div class="flex-col" style="gap: 4px">
            <label class="settings-label">{{ t('settings.smtpLogin') }}</label>
            <div class="flex-row" style="gap: 8px">
              <InputText v-model="channelForm.smtp_user" placeholder="sender@yandex.ru" style="flex: 1" />
              <Button
                outlined
                size="small"
                :loading="smtpDetecting"
                :disabled="!channelForm.smtp_user"
                @click="detectChannelSmtp"
              >
                <i class="fa-solid fa-wand-magic-sparkles" style="margin-right: 4px"></i>{{ t('settings.auto') }}
              </Button>
            </div>
          </div>
          <div class="flex-col" style="gap: 4px">
            <label class="settings-label">SMTP host</label>
            <InputText v-model="channelForm.smtp_host" placeholder="smtp.yandex.ru" />
          </div>
          <div class="flex-col" style="gap: 4px">
            <label class="settings-label">Port</label>
            <InputNumber v-model="channelForm.smtp_port" :min="1" :max="65535" />
          </div>
          <div class="flex-col" style="gap: 4px">
            <label class="settings-label">From</label>
            <InputText v-model="channelForm.smtp_from" placeholder="sender@yandex.ru" />
          </div>
          <div class="flex-col" style="gap: 4px">
            <label class="settings-label">{{ t('settings.smtpPassword') }}</label>
            <InputText
              v-model="channelForm.smtp_password"
              type="password"
              :placeholder="channelForm.has_smtp_password ? t('settings.smtpPasswordSaved') : t('settings.smtpPasswordPlaceholder')"
            />
          </div>
          <div class="flex-row" style="gap: 10px; align-items: center; padding-top: 22px">
            <ToggleSwitch v-model="channelForm.use_tls" input-id="channel-smtp-use-tls" />
            <label for="channel-smtp-use-tls" style="cursor: pointer; font-size: 13px">TLS / STARTTLS</label>
          </div>
        </div>
        <small style="color: var(--p-text-muted-color); font-size: 11px">
          {{ t('settings.emailSmtpHint') }}
        </small>
      </template>
    </div>
    <template #footer>
      <Button text @click="showChannelModal = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submittingChannel" :disabled="submittingChannel" @click="submitChannel(saveChannel)">{{ editingChannelId ? t('common.save') : t('settings.create') }}</Button>
    </template>
  </Dialog>

  <Dialog v-model:visible="showRuleModal" modal :header="editingRuleId ? t('settings.editRule') : t('settings.addRule')" :style="{ width: '500px' }">
    <div class="flex-col" style="gap: 16px">
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('common.name') }}</label>
        <InputText v-model="ruleForm.name" :placeholder="t('settings.ruleNamePlaceholder')" />
      </div>

      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('settings.eventCategory') }}</label>
        <Select
          v-model="ruleForm.event_category"
          :options="eventCategories"
          option-label="label"
          option-value="value"
          @change="onCategoryChange"
        />
      </div>

      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('settings.eventType') }}</label>
        <Select
          v-model="ruleForm.rule_type"
          :options="filteredRuleTypes"
          option-label="label"
          option-value="value"
        />
        <small style="font-size: 11px; color: var(--p-text-muted-color)">
          {{ ruleTypeHint(ruleForm.rule_type) }}
        </small>
      </div>

      <div v-if="showThreshold" class="flex-row" style="gap: 10px; align-items: flex-end">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="settings-label">{{ thresholdLabel }}</label>
          <InputNumber v-model="ruleForm.threshold_value" :use-grouping="false" />
        </div>
        <div class="flex-col" style="gap: 4px; width: 100px">
          <label class="settings-label">{{ t('settings.unit') }}</label>
          <span style="padding: 6px 0; font-size: 13px; color: var(--p-text-muted-color)">{{ thresholdUnit }}</span>
        </div>
      </div>

      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('settings.notificationChannel') }}</label>
        <Select
          v-model="ruleForm.channel_id"
          :options="channels"
          option-label="name"
          option-value="id"
          :placeholder="t('settings.selectChannel')"
        >
          <template #option="{ option }">
            <div class="flex-row" style="align-items: center; gap: 8px">
              <i :class="option.channel_type === 'telegram' ? 'fa-brands fa-telegram' : 'fa-solid fa-envelope'" style="width: 14px"></i>
              {{ option.name }}
              <Tag :value="option.channel_type" severity="secondary" style="font-size: 10px; margin-left: auto" />
            </div>
          </template>
        </Select>
      </div>

      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('common.server') }}</label>
        <Select
          v-model="ruleForm.server_id"
          :options="[{ id: null, name: t('settings.allServersAny') }, ...servers]"
          option-label="name"
          option-value="id"
          :placeholder="t('settings.allServers')"
        />
        <small style="font-size: 11px; color: var(--p-text-muted-color)">
          {{ t('settings.allServersHint') }}
        </small>
      </div>
    </div>
    <template #footer>
      <Button text @click="showRuleModal = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submittingRule" @click="submitRule(saveRule)" :disabled="!ruleForm.name || !ruleForm.channel_id || submittingRule">{{ editingRuleId ? t('common.save') : t('settings.create') }}</Button>
    </template>
  </Dialog>

  <Dialog
    v-model:visible="showScheduleModal"
    modal
    :header="editingScheduleId ? t('settings.editSchedule') : t('settings.newSchedule')"
    :style="{ width: '440px' }"
  >
    <div class="flex-col" style="gap: 14px">
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('common.name') }}</label>
        <InputText v-model="scheduleForm.name" :placeholder="t('settings.scheduleNamePlaceholder')" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('settings.cronExpression') }}</label>
        <CronInput v-model="scheduleForm.cron_expression" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label class="settings-label">{{ t('settings.description') }} <span class="settings-hint">{{ t('settings.optionalParen') }}</span></label>
        <InputText v-model="scheduleForm.description" :placeholder="t('settings.scheduleDescPlaceholder')" />
      </div>
    </div>
    <template #footer>
      <Button text @click="showScheduleModal = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submittingSchedule" @click="submitSchedule(saveSchedule)" :disabled="!scheduleForm.name || !scheduleForm.cron_expression || submittingSchedule">
        {{ editingScheduleId ? t('common.save') : t('settings.create') }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSubmitting } from '../composables/useSubmitting'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import PageHeader from '../components/ui/PageHeader.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import Tag from 'primevue/tag'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import api from '../api/client'
import CronInput from '../components/CronInput.vue'
import { useAuthStore } from '../stores/auth'
import { useTasksStore } from '../stores/tasks'

const { t } = useI18n()
const toast = useToast()
const auth = useAuthStore()

// ── Настройки ИИ (OpenAI) ──
const aiConfig = ref<{ configured: boolean; model: string; source: string }>({ configured: false, model: 'gpt-5.6', source: 'none' })
const aiKeyInput = ref('')
const aiModelInput = ref('gpt-5.6')
const aiSaving = ref(false)

async function loadAiConfig() {
  try {
    const { data } = await api.get('/ai/config')
    aiConfig.value = data
    aiModelInput.value = data.model || 'gpt-5.6'
  } catch { /* ИИ-настройки недоступны — не критично */ }
}
async function saveAiConfig() {
  aiSaving.value = true
  try {
    const body: Record<string, string> = { model: aiModelInput.value }
    if (aiKeyInput.value.trim()) body.api_key = aiKeyInput.value.trim()
    const { data } = await api.put('/ai/config', body)
    aiConfig.value = data
    aiKeyInput.value = ''
    toast.add({ severity: 'success', summary: t('settings.ai.toastSummary'), detail: t('settings.ai.toastSaved'), life: 2500 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.ai.toastSummary'), detail: e?.response?.data?.detail || t('settings.ai.toastSaveFailed'), life: 4000 })
  } finally { aiSaving.value = false }
}
async function clearAiKey() {
  aiSaving.value = true
  try {
    const { data } = await api.put('/ai/config', { api_key: '' })
    aiConfig.value = data
    aiKeyInput.value = ''
    toast.add({ severity: 'info', summary: t('settings.ai.toastSummary'), detail: t('settings.ai.toastKeyDeleted'), life: 2500 })
  } catch { /* ignore */ } finally { aiSaving.value = false }
}
const tasksStore = useTasksStore()
const settingsTab = ref('minio')

// In-flight guard: закрывает окно двойного клика по «Загрузить из PGDG»
// (pgRepoRefreshRunning поднимается лишь после ответа сервера).
const { submitting: pgRefreshSending, submit: submitPgRefresh } = useSubmitting()

// In-flight guard'ы против двойного клика по кнопкам сохранения диалогов
const { submitting: submittingChannel, submit: submitChannel } = useSubmitting()
const { submitting: submittingRule, submit: submitRule } = useSubmitting()
const { submitting: submittingSchedule, submit: submitSchedule } = useSubmitting()

// ── S3 хранилища ─────────────────────────────────────
interface S3StorageRow {
  id: number
  name: string
  endpoint: string
  access_key: string
  secret_key: string
  bucket: string
  secure: boolean
  region: string | null
  sign_version: string
  api_type: string
  swift_project: string | null
  swift_domain: string | null
}
interface ServerRow {
  id: number
  name: string
  storage_id: number | null
  storage_name?: string | null
}

const servers = ref<ServerRow[]>([])
const s3Storages = ref<S3StorageRow[]>([])
const s3StoragesLoading = ref(false)
const showStorageModal = ref(false)
const editingStorageId = ref<number | null>(null)
const storageSaving = ref(false)
const storageTesting = ref(false)
const s3TestingId = ref<number | null>(null)
const s3DeletingId = ref<number | null>(null)
const serverStorageSaving = ref<number | null>(null)
const storageTestResult = ref<{ ok: boolean; message: string } | null>(null)
const storageForm = reactive({
  name: '',
  endpoint: '',
  access_key: '',
  secret_key: '',
  bucket: '',
  secure: false,
  region: '' as string,
  sign_version: 'v4' as string,
  api_type: 's3' as string,
  swift_project: '' as string,
  swift_domain: '' as string,
})

const apiTypeOptions = [
  { label: 'S3 API', value: 's3' },
  { label: 'Swift API (Keystone v3)', value: 'swift' },
]

const signVersionOptions = [
  { label: 'Signature V4', value: 'v4' },
  { label: 'Signature V2', value: 'v2' },
]

const storageAssignOptions = computed(() =>
  s3Storages.value.map((s) => ({ label: s.name, value: s.id }))
)

async function loadServers() {
  try {
    const { data } = await api.get('/servers')
    servers.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.serversTitle'), detail: e?.response?.data?.detail || e?.message || t('settings.loadFailed'), life: 5000 })
  }
}

async function fetchS3Storages() {
  s3StoragesLoading.value = true
  try {
    const { data } = await api.get('/s3-storages')
    s3Storages.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'S3', detail: e.response?.data?.detail || t('settings.loadFailed'), life: 4000 })
  } finally {
    s3StoragesLoading.value = false
  }
}

async function ensureS3Data() {
  await Promise.all([fetchS3Storages(), loadServers()])
}

function resetStorageForm() {
  storageForm.name = ''
  storageForm.endpoint = ''
  storageForm.access_key = ''
  storageForm.secret_key = ''
  storageForm.bucket = ''
  storageForm.secure = false
  storageForm.region = ''
  storageForm.sign_version = 'v4'
  storageForm.api_type = 's3'
  storageForm.swift_project = ''
  storageForm.swift_domain = ''
  storageTestResult.value = null
}

function openStorageModal(row?: S3StorageRow) {
  editingStorageId.value = row?.id ?? null
  resetStorageForm()
  if (row) {
    storageForm.name = row.name
    storageForm.endpoint = row.endpoint
    storageForm.access_key = row.access_key
    storageForm.secret_key = row.secret_key
    storageForm.bucket = row.bucket
    storageForm.secure = row.secure
    storageForm.region = row.region || ''
    storageForm.sign_version = row.sign_version || 'v4'
    storageForm.api_type = row.api_type || 's3'
    storageForm.swift_project = row.swift_project || ''
    storageForm.swift_domain = row.swift_domain || ''
  }
  showStorageModal.value = true
}

async function testStorageForm() {
  storageTesting.value = true
  storageTestResult.value = null
  try {
    const payload = {
      ...storageForm,
      region: storageForm.region.trim() || null,
      swift_project: storageForm.swift_project.trim() || null,
      swift_domain: storageForm.swift_domain.trim() || null,
    }
    const { data } = await api.post('/s3-storages/test', payload)
    storageTestResult.value = data
  } catch (e: any) {
    storageTestResult.value = { ok: false, message: e.response?.data?.detail || t('settings.requestError') }
  } finally {
    storageTesting.value = false
  }
}

async function saveStorage() {
  storageSaving.value = true
  try {
    const payload = {
      ...storageForm,
      region: storageForm.region.trim() || null,
      swift_project: storageForm.swift_project.trim() || null,
      swift_domain: storageForm.swift_domain.trim() || null,
    }
    if (editingStorageId.value) {
      await api.put(`/s3-storages/${editingStorageId.value}`, payload)
      toast.add({ severity: 'success', summary: 'S3', detail: t('settings.storageUpdated'), life: 2500 })
    } else {
      await api.post('/s3-storages', payload)
      toast.add({ severity: 'success', summary: 'S3', detail: t('settings.storageCreated'), life: 2500 })
    }
    showStorageModal.value = false
    await fetchS3Storages()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    storageSaving.value = false
  }
}

async function testSavedStorage(id: number) {
  s3TestingId.value = id
  try {
    const { data } = await api.post(`/s3-storages/${id}/test`)
    toast.add({
      severity: data.ok ? 'success' : 'error',
      summary: 'S3',
      detail: data.message,
      life: 4000,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'S3', detail: e.response?.data?.detail || t('settings.error'), life: 4000 })
  } finally {
    s3TestingId.value = null
  }
}

async function deleteStorage(id: number) {
  s3DeletingId.value = id
  try {
    await api.delete(`/s3-storages/${id}`)
    toast.add({ severity: 'info', summary: 'S3', detail: t('settings.storageDeleted'), life: 2500 })
    await fetchS3Storages()
    await loadServers()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    s3DeletingId.value = null
  }
}

async function assignServerStorage(serverId: number, storageId: number | null) {
  serverStorageSaving.value = serverId
  try {
    const { data } = await api.put(`/servers/${serverId}/storage`, { storage_id: storageId })
    const idx = servers.value.findIndex((s) => s.id === serverId)
    if (idx !== -1) servers.value[idx] = data
    toast.add({ severity: 'success', summary: 'S3', detail: t('settings.bindingSaved'), life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
    await loadServers()
  } finally {
    serverStorageSaving.value = null
  }
}

// ── Уведомления ────────────────────────────────────────
interface NotifHistoryRow {
  id: number
  channel_id: number
  channel_name?: string | null
  rule_id?: number | null
  rule_name?: string | null
  server_name?: string | null
  message: string
  status: string
  sent_at: string
}

const channels = ref<any[]>([])
const rules = ref<any[]>([])
const showChannelHistoryModal = ref(false)
const channelHistoryName = ref('')
const channelHistoryId = ref<number | null>(null)
const channelHistory = ref<NotifHistoryRow[]>([])
const channelHistoryServerId = ref<number | null>(null)
const selectedNotif = ref<NotifHistoryRow | null>(null)
const channelHistoryLoading = ref(false)
const showChannelModal = ref(false)
const showRuleModal = ref(false)
const editingChannelId = ref<number | null>(null)
const editingRuleId = ref<number | null>(null)

const smtpDetecting = ref(false)

const channelForm = reactive({
  name: '',
  channel_type: 'telegram',
  bot_token: '',
  chat_id: '',
  email_to: '',
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_from: '',
  smtp_password: '',
  use_tls: true,
  has_smtp_password: false,
})
const ruleForm = reactive({
  name: '',
  event_category: 'monitoring',
  rule_type: 'max_connections',
  threshold_value: 100,
  channel_id: null as number | null,
  server_id: null as number | null,
})

const eventCategories = computed(() => [
  { label: t('settings.categoryMonitoring'), value: 'monitoring' },
  { label: t('settings.categoryHealth'), value: 'health' },
  { label: t('settings.categoryBackup'), value: 'backup' },
])

const allRuleTypes = computed(() => [
  { label: t('settings.rtMaxConnections'), value: 'max_connections', category: 'monitoring', hint: t('settings.rtMaxConnectionsHint') },
  { label: t('settings.rtLongQuery'), value: 'long_query', category: 'monitoring', hint: t('settings.rtLongQueryHint') },
  { label: t('settings.rtLocks'), value: 'locks', category: 'monitoring', hint: t('settings.rtLocksHint') },
  { label: 'Cache Hit Ratio', value: 'cache_hit_ratio', category: 'monitoring', hint: t('settings.rtCacheHitHint') },
  { label: t('settings.rtDbSize'), value: 'database_size_gb', category: 'monitoring', hint: t('settings.rtDbSizeHint') },
  { label: t('settings.rtServerUnreachable'), value: 'server_unreachable', category: 'health', hint: t('settings.rtServerUnreachableHint') },
  { label: t('settings.rtServerRecovered'), value: 'server_recovered', category: 'health', hint: t('settings.rtServerRecoveredHint') },
  { label: t('settings.rtBackupFailed'), value: 'backup_failed', category: 'backup', hint: t('settings.rtBackupFailedHint') },
  { label: t('settings.rtBackupSuccess'), value: 'backup_success', category: 'backup', hint: t('settings.rtBackupSuccessHint') },
])

const filteredRuleTypes = computed(() =>
  allRuleTypes.value.filter(rt => rt.category === ruleForm.event_category)
)

const showThreshold = computed(() =>
  ['max_connections', 'long_query', 'locks', 'cache_hit_ratio', 'database_size_gb', 'server_unreachable'].includes(ruleForm.rule_type)
)

const thresholdLabel = computed(() => {
  const map: Record<string, string> = {
    max_connections: t('settings.thMaxConnections'),
    long_query: t('settings.thLongQuery'),
    locks: t('settings.thLocks'),
    cache_hit_ratio: t('settings.thCacheHit'),
    database_size_gb: t('settings.thDbSize'),
    server_unreachable: t('settings.thServerUnreachable'),
  }
  return map[ruleForm.rule_type] || t('settings.thDefault')
})

const thresholdUnit = computed(() => {
  const map: Record<string, string> = {
    max_connections: t('settings.unitPcs'),
    long_query: t('settings.unitSeconds'),
    locks: t('settings.unitPcs'),
    cache_hit_ratio: '%',
    database_size_gb: 'GB',
    server_unreachable: t('settings.unitPcs'),
  }
  return map[ruleForm.rule_type] || ''
})

function ruleTypeHint(type: string): string {
  return allRuleTypes.value.find(rt => rt.value === type)?.hint || ''
}

function ruleTypeLabel(type: string): string {
  return allRuleTypes.value.find(rt => rt.value === type)?.label || type
}

function ruleCategory(type: string): { label: string; severity: string } {
  const rt = allRuleTypes.value.find(x => x.value === type)
  if (rt?.category === 'backup') return { label: t('settings.catBackup'), severity: 'warn' }
  if (rt?.category === 'health') return { label: t('settings.catHealth'), severity: 'danger' }
  return { label: t('settings.categoryMonitoring'), severity: 'info' }
}

function onCategoryChange() {
  const first = filteredRuleTypes.value[0]
  if (first) ruleForm.rule_type = first.value
}

function openRuleModal(rule?: any) {
  editingRuleId.value = rule?.id ?? null
  if (rule) {
    ruleForm.name = rule.name
    const cat = allRuleTypes.value.find(rt => rt.value === rule.rule_type)?.category ?? 'monitoring'
    ruleForm.event_category = cat
    ruleForm.rule_type = rule.rule_type
    try {
      const th = JSON.parse(rule.threshold_json)
      ruleForm.threshold_value = th.max_gb ?? th.fail_count ?? th.max ?? th.max_seconds ?? th.min ?? 100
    } catch { ruleForm.threshold_value = 100 }
    ruleForm.channel_id = rule.channel_id
    ruleForm.server_id = rule.server_id ?? null
  } else {
    ruleForm.name = ''
    ruleForm.event_category = 'monitoring'
    ruleForm.rule_type = 'max_connections'
    ruleForm.threshold_value = 100
    ruleForm.channel_id = channels.value[0]?.id ?? null
    ruleForm.server_id = null
  }
  showRuleModal.value = true
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, '')
}

function notifPreview(message: string): string {
  const text = stripHtml(message).replace(/\s+/g, ' ').trim()
  if (text.length <= 48) return text
  return `${text.slice(0, 48)}…`
}

function notifRowClass(data: NotifHistoryRow): string {
  return data.status === 'failed' ? 'channel-history-row--failed' : 'channel-history-row'
}

async function showChannelHistory(channel: { id: number; name: string }) {
  channelHistoryId.value = channel.id
  channelHistoryName.value = channel.name
  channelHistoryServerId.value = null
  selectedNotif.value = null
  showChannelHistoryModal.value = true
  await fetchChannelHistory()
}

async function fetchChannelHistory() {
  if (!channelHistoryId.value) return
  channelHistoryLoading.value = true
  try {
    const params: Record<string, unknown> = {
      limit: 100,
      channel_id: channelHistoryId.value,
    }
    if (channelHistoryServerId.value !== null) {
      params.server_id = channelHistoryServerId.value
    }
    const { data } = await api.get('/notifications/history', { params })
    channelHistory.value = data
    selectedNotif.value =
      data.find((row: NotifHistoryRow) => row.status === 'failed') ?? data[0] ?? null
  } catch {
    toast.add({ severity: 'error', summary: t('settings.loadLogFailed'), life: 3000 })
  } finally {
    channelHistoryLoading.value = false
  }
}

async function copyNotifMessage() {
  const text = selectedNotif.value?.message
  if (!text) return
  try {
    await navigator.clipboard.writeText(stripHtml(text))
    toast.add({ severity: 'success', summary: t('settings.copied'), life: 2000 })
  } catch {
    toast.add({ severity: 'error', summary: t('settings.copyFailed'), life: 2500 })
  }
}

function resetChannelForm() {
  channelForm.name = ''
  channelForm.channel_type = 'telegram'
  channelForm.bot_token = ''
  channelForm.chat_id = ''
  channelForm.email_to = ''
  channelForm.smtp_host = ''
  channelForm.smtp_port = 587
  channelForm.smtp_user = ''
  channelForm.smtp_from = ''
  channelForm.smtp_password = ''
  channelForm.use_tls = true
  channelForm.has_smtp_password = false
}

function openChannelModal(ch?: any) {
  editingChannelId.value = ch?.id ?? null
  resetChannelForm()
  if (ch) {
    channelForm.name = ch.name
    channelForm.channel_type = ch.channel_type
    try {
      const cfg = JSON.parse(ch.config_json)
      channelForm.bot_token = cfg.bot_token ?? ''
      channelForm.chat_id = cfg.chat_id ?? ''
      channelForm.email_to = cfg.to ?? ''
      channelForm.smtp_host = cfg.smtp_host ?? ''
      channelForm.smtp_port = cfg.smtp_port ?? 587
      channelForm.smtp_user = cfg.smtp_user ?? ''
      channelForm.smtp_from = cfg.smtp_from ?? ''
      channelForm.use_tls = cfg.use_tls ?? true
      channelForm.has_smtp_password = cfg.has_smtp_password ?? false
    } catch { /* ignore */ }
  }
  showChannelModal.value = true
}

// Сбрасываем результаты поиска при открытии диалога
watch(showChannelModal, (v) => {
  if (v) { foundChats.value = []; chatIdSearched.value = false }
})

// ── Поиск Chat ID через getUpdates ─────────────────────
interface FoundChat { id: number; name: string; type: string }
const foundChats = ref<FoundChat[]>([])
const chatIdLoading = ref(false)
const chatIdSearched = ref(false)

async function fetchChatIds() {
  if (!channelForm.bot_token) return
  chatIdLoading.value = true
  chatIdSearched.value = false
  foundChats.value = []
  try {
    const resp = await fetch(
      `https://api.telegram.org/bot${channelForm.bot_token}/getUpdates?limit=100&offset=-100`
    )
    const json = await resp.json()
    if (!json.ok) {
      toast.add({ severity: 'error', summary: 'Telegram', detail: json.description || t('settings.apiError'), life: 4000 })
      return
    }
    const seen = new Set<number>()
    const chats: FoundChat[] = []
    for (const upd of json.result ?? []) {
      const chat = upd.message?.chat ?? upd.channel_post?.chat ?? upd.my_chat_member?.chat
      if (!chat) continue
      if (seen.has(chat.id)) continue
      seen.add(chat.id)
      const name = chat.title ?? [chat.first_name, chat.last_name].filter(Boolean).join(' ') ?? `#${chat.id}`
      chats.push({ id: chat.id, name, type: chat.type ?? 'unknown' })
    }
    foundChats.value = chats
    // Автовыбор если только один чат
    if (chats.length === 1) channelForm.chat_id = String(chats[0].id)
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: t('settings.telegramApiError'), life: 4000 })
  } finally {
    chatIdLoading.value = false
    chatIdSearched.value = true
  }
}

const typeOptions = [
  { label: 'Telegram', value: 'telegram' },
  { label: 'Email', value: 'email' },
]
async function detectChannelSmtp() {
  smtpDetecting.value = true
  try {
    const { data } = await api.post('/notifications/smtp/detect', { email: channelForm.smtp_user })
    channelForm.smtp_host = data.smtp_host
    channelForm.smtp_port = data.smtp_port
    channelForm.smtp_user = data.smtp_user
    channelForm.smtp_from = data.smtp_from
    channelForm.use_tls = data.use_tls
    toast.add({
      severity: 'success',
      summary: 'SMTP',
      detail: t('settings.smtpDetected', { domain: data.detected_domain }),
      life: 2500,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'SMTP', detail: e.response?.data?.detail || t('settings.detectFailed'), life: 4000 })
  } finally {
    smtpDetecting.value = false
  }
}

async function fetchData() {
  try {
    const [c, r] = await Promise.all([
      api.get('/notifications/channels'),
      api.get('/notifications/rules'),
    ])
    channels.value = c.data
    rules.value = r.data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.channelsAndRules'), detail: e?.response?.data?.detail || e?.message || t('settings.loadFailed'), life: 5000 })
  }
}

async function saveChannel() {
  const config = channelForm.channel_type === 'telegram'
    ? { bot_token: channelForm.bot_token, chat_id: channelForm.chat_id }
    : {
        to: channelForm.email_to,
        smtp_host: channelForm.smtp_host,
        smtp_port: channelForm.smtp_port,
        smtp_user: channelForm.smtp_user,
        smtp_from: channelForm.smtp_from || channelForm.smtp_user,
        use_tls: channelForm.use_tls,
        ...(channelForm.smtp_password ? { smtp_password: channelForm.smtp_password } : {}),
      }
  try {
    if (editingChannelId.value) {
      await api.put(`/notifications/channels/${editingChannelId.value}`, { name: channelForm.name, config })
      toast.add({ severity: 'success', summary: t('settings.channelUpdated'), life: 2500 })
    } else {
      await api.post('/notifications/channels', { name: channelForm.name, channel_type: channelForm.channel_type, config })
      toast.add({ severity: 'success', summary: t('settings.channelCreated'), life: 2500 })
    }
    showChannelModal.value = false
    fetchData()
  } catch (e: any) { toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 }) }
}

async function toggleChannel(id: number, isActive: boolean) {
  try {
    const { data } = await api.put(`/notifications/channels/${id}`, { is_active: isActive })
    const idx = channels.value.findIndex((c: any) => c.id === id)
    if (idx !== -1) channels.value[idx] = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

const testingChannelId = ref<number | null>(null)
async function testChannel(id: number) {
  testingChannelId.value = id
  try {
    const { data } = await api.post(`/notifications/channels/${id}/test`)
    toast.add({
      severity: data.success ? 'success' : 'error',
      summary: t('common.test'),
      detail: data.message || (data.success ? t('settings.sent') : t('settings.error')),
      life: 4000,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || t('settings.sendFailed'), life: 4000 })
  } finally {
    testingChannelId.value = null
  }
}

async function deleteChannel(id: number) {
  try {
    await api.delete(`/notifications/channels/${id}`)
    toast.add({ severity: 'info', summary: t('settings.channelDeleted'), life: 2000 })
    fetchData()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

async function saveRule() {
  const threshold = buildThreshold(ruleForm.rule_type, ruleForm.threshold_value)
  try {
    if (editingRuleId.value) {
      const { data } = await api.put(`/notifications/rules/${editingRuleId.value}`, {
        name: ruleForm.name,
        rule_type: ruleForm.rule_type,
        threshold,
        channel_id: ruleForm.channel_id,
        server_id: ruleForm.server_id,
      })
      const idx = rules.value.findIndex((r: any) => r.id === editingRuleId.value)
      if (idx !== -1) rules.value[idx] = data
      toast.add({ severity: 'success', summary: t('settings.ruleUpdated'), life: 2500 })
    } else {
      await api.post('/notifications/rules', {
        name: ruleForm.name,
        rule_type: ruleForm.rule_type,
        threshold,
        channel_id: ruleForm.channel_id,
        server_id: ruleForm.server_id,
      })
      toast.add({ severity: 'success', summary: t('settings.ruleCreated'), life: 2500 })
      await fetchData()
    }
    showRuleModal.value = false
  } catch (e: any) { toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 }) }
}

function buildThreshold(ruleType: string, value: number): Record<string, number> {
  if (ruleType === 'long_query') return { max_seconds: value }
  if (ruleType === 'cache_hit_ratio') return { min: value }
  if (ruleType === 'database_size_gb') return { max_gb: value }
  if (ruleType === 'server_unreachable') return { fail_count: value }
  if (['backup_failed', 'backup_success', 'server_recovered'].includes(ruleType)) return {}
  return { max: value }
}

async function toggleRule(id: number, isActive: boolean) {
  try {
    const { data } = await api.patch(`/notifications/rules/${id}`, { is_active: isActive })
    const idx = rules.value.findIndex(r => r.id === id)
    if (idx !== -1) rules.value[idx] = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

async function deleteRule(id: number) {
  try {
    await api.delete(`/notifications/rules/${id}`)
    rules.value = rules.value.filter(r => r.id !== id)
    toast.add({ severity: 'info', summary: t('settings.ruleDeleted'), life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

function formatDate(iso: string) {
  try {
    const utc = iso && !iso.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(iso) ? iso + 'Z' : iso
    return new Date(utc).toLocaleString('ru-RU')
  } catch { return iso }
}

// ── Расписания ─────────────────────────────────────────
const cronSchedules = ref<any[]>([])
const showScheduleModal = ref(false)
const editingScheduleId = ref<number | null>(null)
const scheduleForm = reactive({ name: '', cron_expression: '', description: '' })

async function fetchSchedules() {
  try {
    const { data } = await api.get('/cron-schedules')
    cronSchedules.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.schedulesTitle'), detail: e?.response?.data?.detail || e?.message || t('settings.loadFailed'), life: 5000 })
  }
}

function openScheduleModal(sc?: any) {
  editingScheduleId.value = sc?.id ?? null
  scheduleForm.name = sc?.name ?? ''
  scheduleForm.cron_expression = sc?.cron_expression ?? ''
  scheduleForm.description = sc?.description ?? ''
  showScheduleModal.value = true
}

async function saveSchedule() {
  const payload = { name: scheduleForm.name, cron_expression: scheduleForm.cron_expression, description: scheduleForm.description }
  try {
    if (editingScheduleId.value) {
      await api.put(`/cron-schedules/${editingScheduleId.value}`, payload)
      toast.add({ severity: 'success', summary: t('settings.scheduleUpdated'), life: 2500 })
    } else {
      await api.post('/cron-schedules', payload)
      toast.add({ severity: 'success', summary: t('settings.scheduleCreated'), life: 2500 })
    }
    showScheduleModal.value = false
    fetchSchedules()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

async function deleteSchedule(id: number) {
  try {
    await api.delete(`/cron-schedules/${id}`)
    cronSchedules.value = cronSchedules.value.filter((s: any) => s.id !== id)
    toast.add({ severity: 'info', summary: t('settings.deleted'), life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('settings.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

function cronHint(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return t('settings.cronDesc.invalid')
  const [min, hour, dom, month, dow] = parts
  if (min === '0' && hour !== '*' && dom === '*' && month === '*' && dow === '*')
    return t('settings.cronDesc.everyDay', { h: hour.padStart(2, '0') })
  if (min === '0' && hour === '*') return t('settings.cronDesc.everyHour')
  if (min === '0' && hour.includes(',')) {
    const times = hour.split(',').map(h => h.padStart(2, '0') + ':00').join(t('settings.cronDesc.timeSep'))
    return t('settings.cronDesc.everyDayMulti', { times })
  }
  if (min === '0' && hour !== '*' && dow !== '*') {
    const days = [
      t('settings.cronDesc.dow0'), t('settings.cronDesc.dow1'), t('settings.cronDesc.dow2'),
      t('settings.cronDesc.dow3'), t('settings.cronDesc.dow4'), t('settings.cronDesc.dow5'),
      t('settings.cronDesc.dow6'),
    ]
    return t('settings.cronDesc.everyDow', { d: days[+dow] ?? dow, h: hour.padStart(2,'0') })
  }
  if (hour.startsWith('*/')) return t('settings.cronDesc.everyNHours', { n: hour.slice(2) })
  return `cron: ${expr}`
}

// ── PG Client Versions ────────────────────────────────
interface PgVersionInfo {
  id: number
  major: number
  source: string
  note: string | null
  installed: boolean
  requested: boolean
  available_in_repo: boolean
  candidate: string | null
  bin_path: string | null
  servers: { id: number; name: string }[]
}
interface AvailablePgPackage {
  major: number
  package: string
  candidate: string | null
  installed: boolean
}
const pgVersions = ref<PgVersionInfo[]>([])
const availablePgPackages = ref<AvailablePgPackage[]>([])
const pgVersionsLoading = ref(false)
const availablePgLoading = ref(false)
const pgInstallMajor = ref<number | null>(null)
const pgUninstallMajor = ref<number | null>(null)
const pgCatalogAdding = ref(false)
const pgCatalogRemoving = ref<number | null>(null)
const newPgMajor = ref<number | null>(null)

const pgRepoRefreshRunning = computed(() => !!tasksStore.findPgRepoRefreshTask())

const catalogAddOptions = computed(() =>
  availablePgPackages.value
    .filter((p) => !pgVersions.value.some((v) => v.major === p.major))
    .map((p) => ({
      label: p.candidate ? `PostgreSQL ${p.major} — ${p.candidate}` : `PostgreSQL ${p.major}`,
      value: p.major,
    }))
)

function pgClientSourceLabel(source: string) {
  return source === 'requested' ? t('settings.sourceRequested') : t('settings.sourceManual')
}

async function ensurePgClientData() {
  if (!auth.isSuperAdmin) return
  // Только чтение уже известного каталога. Загрузку из PGDG (тяжёлая Celery-задача
  // apt/PGDG на платформе) НЕ запускаем автоматически — только по кнопке «Загрузить из PGDG».
  await Promise.all([fetchPgVersions(), fetchAvailableFromRepo()])
}

async function fetchAvailableFromRepo() {
  if (!auth.isSuperAdmin) return
  availablePgLoading.value = true
  try {
    const { data } = await api.get('/pg-client-versions/available')
    availablePgPackages.value = data.packages || []
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'PGDG',
      detail: e.response?.data?.detail || t('settings.repoLoadFailed'),
      life: 5000,
    })
  } finally {
    availablePgLoading.value = false
  }
}

async function refreshAvailableFromRepo() {
  if (!auth.isSuperAdmin || pgRepoRefreshRunning.value) return
  try {
    const { data } = await api.post('/pg-client-versions/available/refresh')
    if (data.task_id) {
      tasksStore.seedPgClientTask(data.task_id, 0, 'refresh')
    }
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'PGDG',
      detail: e.response?.data?.detail || t('settings.pgdgStartFailed'),
      life: 5000,
    })
  }
}

async function fetchPgVersions() {
  if (!auth.isSuperAdmin) return
  pgVersionsLoading.value = true
  try {
    const { data } = await api.get('/pg-client-versions')
    pgVersions.value = data.items || []
  } catch {} finally {
    pgVersionsLoading.value = false
  }
}

async function addPgClientToCatalog() {
  if (!newPgMajor.value || pgCatalogAdding.value) return
  pgCatalogAdding.value = true
  try {
    await api.post('/pg-client-versions', { major: newPgMajor.value })
    toast.add({
      severity: 'success',
      summary: t('settings.pgClientsTitle'),
      detail: t('settings.pgAddedToCatalog', { major: newPgMajor.value }),
      life: 2500,
    })
    newPgMajor.value = null
    await fetchPgVersions()
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: t('settings.error'),
      detail: e.response?.data?.detail || t('settings.addVersionFailed'),
      life: 4000,
    })
  } finally {
    pgCatalogAdding.value = false
  }
}

async function removePgClientFromCatalog(major: number) {
  pgCatalogRemoving.value = major
  try {
    await api.delete(`/pg-client-versions/${major}/catalog`)
    toast.add({
      severity: 'info',
      summary: t('settings.pgClientsTitle'),
      detail: t('settings.pgRemovedFromCatalog', { major }),
      life: 2500,
    })
    await fetchPgVersions()
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: t('settings.error'),
      detail: e.response?.data?.detail || t('settings.removeFromCatalogFailed'),
      life: 4000,
    })
  } finally {
    pgCatalogRemoving.value = null
  }
}

async function installPgClient(major: number) {
  if (pgInstallMajor.value === major) return
  pgInstallMajor.value = major
  try {
    const { data } = await api.post(`/pg-client-versions/${major}/install`)
    if (data.task_id) {
      tasksStore.seedPgClientTask(data.task_id, major, 'install')
    } else {
      toast.add({
        severity: 'info',
        summary: t('settings.pgClientTitle'),
        detail: data.message || t('settings.pgAlreadyInstalled', { major }),
        life: 3000,
      })
      await fetchPgVersions()
      await fetchAvailableFromRepo()
    }
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: t('settings.installError'),
      detail: e.response?.data?.detail || t('settings.installStartFailed'),
      life: 5000,
    })
  } finally {
    pgInstallMajor.value = null
  }
}

async function uninstallPgClient(major: number) {
  if (pgUninstallMajor.value === major) return
  pgUninstallMajor.value = major
  try {
    const { data } = await api.delete(`/pg-client-versions/${major}`)
    if (data.task_id) {
      tasksStore.seedPgClientTask(data.task_id, major, 'uninstall')
    } else {
      toast.add({
        severity: 'info',
        summary: t('settings.pgClientTitle'),
        detail: data.message || t('settings.pgNotInstalled', { major }),
        life: 3000,
      })
      await fetchPgVersions()
      await fetchAvailableFromRepo()
    }
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: t('settings.uninstallError'),
      detail: e.response?.data?.detail || t('settings.uninstallStartFailed'),
      life: 5000,
    })
  } finally {
    pgUninstallMajor.value = null
  }
}

watch(
  () => tasksStore.tasks.filter(t => t.type === 'pg_client' && (t.done || t.failed)).length,
  () => {
    if (settingsTab.value === 'pg-versions') {
      ensurePgClientData()
    }
  }
)

watch(showChannelHistoryModal, (open) => {
  if (!open) {
    channelHistoryId.value = null
    selectedNotif.value = null
    channelHistory.value = []
  }
})

watch(settingsTab, (tab) => {
  if (tab === 'pg-versions') {
    ensurePgClientData()
  }
  if (tab === 'minio') {
    ensureS3Data()
  }
})

onMounted(() => {
  loadServers()
  fetchData()
  fetchSchedules()
  if (auth.isSuperAdmin) loadAiConfig()
  if (auth.isSuperAdmin && settingsTab.value === 'pg-versions') {
    ensurePgClientData()
  }
  if (settingsTab.value === 'minio') {
    ensureS3Data()
  }
})
</script>

<style scoped>
.settings-label { font-size: 13px; color: var(--p-text-muted-color); margin-bottom: 2px; }
.settings-hint { font-size: 11px; color: var(--p-text-muted-color); margin-left: 4px; font-weight: 400; }

.s3-servers-section {
  margin-top: 24px;
}
.s3-servers-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 4px;
}
.s3-servers-hint {
  font-size: 12px;
  color: var(--p-text-muted-color);
  margin-bottom: 12px;
}

.minio-info-banner, .minio-configured-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
}
.minio-info-banner {
  background: var(--p-blue-50);
  color: var(--p-blue-700);
  border: 1px solid var(--p-blue-200);
}
.minio-configured-banner {
  background: var(--p-green-50);
  color: var(--p-green-700);
  border: 1px solid var(--p-green-200);
}

.minio-test-result {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
}
.minio-test-result.ok { background: var(--p-green-50); color: var(--p-green-700); border: 1px solid var(--p-green-200); }
.minio-test-result.fail { background: var(--p-red-50); color: var(--p-red-700); border: 1px solid var(--p-red-200); }

/* ── Chat ID finder ── */
.found-chats {
  border: 1px solid var(--p-surface-200);
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--p-surface-50);
}
.app-dark .found-chats { border-color: #2d3f57; background: #1c2a3f; }
.found-chat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}
.found-chat-item:hover { background: var(--p-surface-100); }
.app-dark .found-chat-item:hover { background: rgba(255,255,255,0.05); }
.found-chat-item.selected {
  background: rgba(52, 211, 153, 0.10);
  border-color: #34d399;
}
.found-chat-name { flex: 1; font-weight: 500; }
.found-chat-id {
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 11px;
  background: var(--p-surface-200);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}
.app-dark .found-chat-id { background: #243047; }
.found-chats-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  color: var(--p-text-muted-color);
  background: var(--p-surface-50);
  border: 1px solid var(--p-surface-200);
}
.app-dark .found-chats-empty { background: #1c2a3f; border-color: #2d3f57; }

/* ── PG Client Versions ── */
.pg-versions-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--p-text-muted-color);
  background: var(--p-surface-50);
  border: 1px solid var(--p-surface-200);
}

.pg-repo-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
.pg-repo-hint--muted {
  font-style: italic;
}

.channel-smtp-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}
@media (max-width: 520px) {
  .channel-smtp-grid { grid-template-columns: 1fr; }
}

.pg-version-row {
  border: 1px solid var(--p-surface-200);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.app-dark .pg-version-row { border-color: #2d3f57; }

.settings-muted {
  color: var(--p-text-muted-color);
  font-size: 12px;
}

.channel-history-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.channel-history-toolbar {
  gap: 8px;
  flex-wrap: wrap;
}

.channel-history-table {
  width: 100%;
}

.channel-history-table :deep(.p-datatable-table) {
  table-layout: fixed;
  width: 100%;
}

.channel-history-clip {
  display: block;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-history-table :deep(.channel-history-row) {
  cursor: pointer;
}

.channel-history-table :deep(.channel-history-row--failed > td) {
  background: color-mix(in srgb, var(--p-red-500) 4%, transparent);
}

.channel-history-detail {
  border: 1px solid var(--p-surface-200);
  border-radius: 8px;
  padding: 12px;
  background: var(--p-surface-50);
  min-width: 0;
}

.app-dark .channel-history-detail {
  background: #141e2e;
  border-color: #2d3f57;
}

.channel-history-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.channel-history-detail-title {
  font-size: 13px;
  font-weight: 600;
}

.channel-history-message {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid var(--p-surface-200);
  background: var(--p-surface-0);
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.app-dark .channel-history-message {
  background: #1c2a3f;
  border-color: #2d3f57;
  color: #e2e8f0;
}

.channel-history-hint {
  margin: 0;
}

.pg-version-info {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.pg-version-actions {
  margin-top: 10px;
}

.pg-version-num {
  font-size: 15px;
  font-weight: 700;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  color: var(--p-primary-color);
}

.pg-version-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
}
.status-ok {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}
.status-missing {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.pg-version-fix {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #d97706;
  padding: 7px 10px;
  background: rgba(245, 158, 11, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(245, 158, 11, 0.2);
}
.pg-version-fix code {
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  background: rgba(245, 158, 11, 0.15);
  padding: 1px 5px;
  border-radius: 3px;
}

.pg-version-servers {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pg-version-server-chip {
  font-size: 12px;
  background: var(--p-surface-100);
  border-radius: 10px;
  padding: 2px 10px;
  color: var(--p-text-muted-color);
}
.app-dark .minio-info-banner {
  background: rgba(59, 130, 246, 0.12);
  color: #93c5fd;
  border-color: rgba(59, 130, 246, 0.35);
}
.app-dark .minio-configured-banner {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.35);
}
.app-dark .minio-test-result.ok {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.35);
}
.app-dark .minio-test-result.fail {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.35);
}
.app-dark .pg-versions-empty {
  background: #1c2a3f;
  border-color: #2d3f57;
}
.app-dark .status-ok { color: #4ade80; }
.app-dark .status-missing { color: #f87171; }
.app-dark .pg-version-server-chip {
  background: #243047;
  color: #cbd5e1;
}

.running-cell {
  gap: 10px;
  align-items: center;
  padding: 6px 10px;
  background: var(--p-yellow-50);
  border: 1px solid var(--p-yellow-200);
  border-radius: 6px;
  transition: background 0.15s;
}
.running-cell:hover { background: var(--p-yellow-100); }
.running-icon { color: var(--p-yellow-600); }
.running-text {
  font-size: 12px;
  color: var(--p-yellow-700);
  font-weight: 600;
}
.running-pct {
  font-size: 11px;
  color: var(--p-yellow-700);
  margin-left: auto;
}
:global(.app-dark) .running-cell {
  background: rgba(234, 179, 8, 0.08);
  border-color: rgba(234, 179, 8, 0.3);
}
:global(.app-dark) .running-text,
:global(.app-dark) .running-pct { color: #facc15; }

.ai-settings-form { display: flex; flex-direction: column; gap: 14px; max-width: 560px; }
.ai-settings-field { display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; }
.ai-settings-input {
  padding: 10px 12px;
  border: 1px solid var(--p-inputtext-border-color, #cbd5e1);
  border-radius: 8px;
  background: var(--p-inputtext-background, #fff);
  color: var(--p-inputtext-color, inherit);
  font: inherit;
}
</style>
