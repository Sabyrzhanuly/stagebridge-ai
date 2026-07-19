<template>
  <PageHeader :title="t('backups.title')" :subtitle="t('backups.subtitle')">
    <template #actions>
      <Button outlined @click="reloadAll" :loading="historyLoading || serversLoading">
        <i class="fa-solid fa-rotate btn-icon-left" aria-hidden="true"></i>{{ t('common.refresh') }}
      </Button>
    </template>
  </PageHeader>

  <AlertBanner v-if="healthStore.workerOnline === false" severity="warn">
    <strong>{{ t('backups.workerOfflineTitle') }}</strong> {{ t('backups.workerOfflineText') }} <code>worker</code>.
  </AlertBanner>

  <AlertBanner v-else-if="selectedServer && orgStorages.length === 0 && !selectedServer.storage_id" severity="warn">
    <strong>{{ t('backups.noStorageTitle') }}</strong> {{ t('backups.noStorageText') }}
  </AlertBanner>

  <div class="card-panel">
    <div class="card-panel-title">
      <span><i class="fa-solid fa-server" style="margin-right: 8px"></i>{{ t('common.server') }}</span>
    </div>
    <div class="flex-row" style="gap: 12px; align-items: center">
      <Select
        v-model="selectedServerId"
        :options="serverOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('backups.selectServer')"
        filter
        :loading="serversLoading"
        style="width: 360px"
      />
      <Button outlined size="small" @click="loadServers" :loading="serversLoading">
        <i class="fa-solid fa-rotate"></i>
      </Button>
    </div>

    <div v-if="selectedServerId" style="margin-top: 16px">
      <DataTable :value="userDatabases" :loading="dbsLoading" :scrollable="true" scroll-height="380px" striped-rows>
        <template #empty>
          <div class="muted" style="padding: 20px; text-align: center">{{ t('backups.noUserDbs') }}</div>
        </template>
        <Column field="datname" :header="t('common.database')" sortable style="width: 200px" />
        <Column field="owner" :header="t('backups.owner')" style="width: 120px" />
        <Column field="size" :header="t('backups.size')" sortable style="width: 110px" />
        <Column :header="t('backups.lastBackup')" style="width: 220px">
          <template #body="{ data }">
            <div v-if="lastBackupFor(data.datname)" class="flex-row" style="gap: 4px">
              <Tag
                :severity="statusSeverity(lastBackupFor(data.datname)!.status)"
                :value="lastBackupFor(data.datname)!.status === 'success' ? formatDate(lastBackupFor(data.datname)!.started_at) : lastBackupFor(data.datname)!.status"
              />
              <Tag
                v-if="lastBackupFor(data.datname)!.file_size"
                severity="secondary"
                :value="formatBytes(lastBackupFor(data.datname)!.file_size!)"
              />
            </div>
            <span v-else class="muted">{{ t('backups.noneLower') }}</span>
          </template>
        </Column>
          <Column :header="t('common.actions')" style="width: 320px">
            <template #body="{ data }">
              <div v-if="activeTaskFor(data.datname)" class="flex-row running-cell" @click="openTaskProgress(data.datname)">
                <i class="fa-solid fa-spinner fa-spin running-icon"></i>
                <span class="running-text">{{ activeTaskFor(data.datname)?.stage }}</span>
                <span class="running-pct">{{ tasksStore.progressPercent(activeTaskFor(data.datname)!) }}%</span>
                <Button size="small" text severity="secondary" @click.stop="openTaskProgress(data.datname)">
                  <i class="fa-solid fa-up-right-from-square"></i>
                </Button>
              </div>
              <div v-else-if="lastBackupFor(data.datname)?.status === 'running'" class="flex-row running-cell running-cell-detached">
                <i class="fa-solid fa-spinner fa-spin running-icon"></i>
                <span class="running-text">{{ lastBackupFor(data.datname)?.stage || t('backups.inProgress') }}</span>
                <span class="running-hint">{{ t('backups.noLiveData') }}</span>
              </div>
              <div v-else class="flex-row" style="gap: 6px">
                <Button size="small" @click="openBackupDialog(data.datname)">
                  <i class="fa-solid fa-box-archive" style="margin-right: 4px"></i>{{ t('backups.backup') }}
                </Button>
                <Button size="small" outlined @click="openScheduleForDb(data.datname)">
                  <i class="fa-solid fa-calendar" style="margin-right: 4px"></i>{{ t('backups.schedule') }}
                </Button>
              </div>
            </template>
          </Column>
      </DataTable>

      <AiInsight
        :label="t('backups.aiLabel')"
        endpoint="/ai/backup-analysis"
        :payload="() => ({ payload: JSON.stringify({ server: selectedServer, databases: userDatabases.map(d => ({ name: d.datname, size: d.size, last_backup: lastBackupFor(d.datname) || null })) }) })"
        :sections="[{ key: 'checks', title: t('backups.aiSecChecks') }, { key: 'cautions', title: t('backups.aiSecCautions') }]"
        badge-field="risk"
      />
    </div>
    <div v-else class="muted" style="padding: 20px; text-align: center">{{ t('backups.selectServerForDbs') }}</div>
  </div>

  <div class="card-panel card-panel--tabs">
    <Tabs value="history">
      <TabList>
        <Tab value="history"><i class="fa-solid fa-clock-rotate-left" style="margin-right: 8px"></i>{{ t('backups.historyTab') }}</Tab>
        <Tab value="restore"><i class="fa-solid fa-arrow-rotate-left" style="margin-right: 8px"></i>{{ t('backups.restore') }}</Tab>
        <Tab value="restore-history"><i class="fa-solid fa-clock-rotate-left" style="margin-right: 8px"></i>{{ t('backups.restoreHistory') }}</Tab>
        <Tab value="schedules"><i class="fa-solid fa-calendar-days" style="margin-right: 8px"></i>{{ t('backups.schedules') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="history">
          <div class="flex-row tab-panel-toolbar">
            <span style="font-size: 13px">{{ t('common.server') }}:</span>
            <Select
              v-model="historyServerFilter"
              :options="[{ label: t('backups.allServers'), value: null }, ...serverOptions]"
              option-label="label"
              option-value="value"
              :placeholder="t('common.all')"
              style="width: 220px"
            />
            <span class="spacer" />
            <Button
              v-if="selectedRows.length > 0"
              severity="danger"
              outlined
              size="small"
              :loading="deleteLoading"
              @click="confirmDeleteSelected"
            >
              <i class="fa-solid fa-trash" style="margin-right: 6px"></i>{{ t('backups.deleteSelected', { count: selectedRows.length }) }}
            </Button>
          </div>
          <DataTable
            v-model:selection="selectedRows"
            :value="filteredHistory"
            :loading="historyLoading"
            :paginator="filteredHistory.length > 25"
            :rows="25"
            striped-rows
            scroll-height="500px"
            data-key="id"
          >
            <Column selection-mode="multiple" style="width: 40px" />
            <Column field="id" header="ID" style="width: 70px" sortable />
            <Column field="server_id" :header="t('common.server')" style="width: 90px" />
            <Column field="database_name" :header="t('backups.db')" style="width: 140px" />
            <Column field="storage_name" :header="t('backups.storage')" style="width: 140px">
              <template #body="{ data }">
                <span v-if="data.storage_name">{{ data.storage_name }}</span>
                <span v-else-if="data.storage_id" class="muted">#{{ data.storage_id }}</span>
                <span v-else class="muted">—</span>
              </template>
            </Column>
            <Column field="status" :header="t('common.status')" style="width: 110px">
              <template #body="{ data }">
                <Tag :severity="statusSeverity(data.status)" :value="data.status" />
              </template>
            </Column>
            <Column field="backup_format" :header="t('backups.format')" style="width: 90px">
              <template #body="{ data }">
                <Tag severity="secondary" :value="data.backup_format || 'custom'" style="font-size: 11px" />
              </template>
            </Column>
            <Column field="file_size" :header="t('backups.size')" style="width: 100px">
              <template #body="{ data }">{{ data.file_size ? formatBytes(data.file_size) : '—' }}</template>
            </Column>
            <Column field="duration_seconds" :header="t('backups.duration')" style="width: 80px">
              <template #body="{ data }">{{ data.duration_seconds ? t('backups.secondsShort', { n: data.duration_seconds }) : '—' }}</template>
            </Column>
            <Column field="started_at" :header="t('backups.date')" style="width: 170px" sortable>
              <template #body="{ data }">{{ formatDate(data.started_at) }}</template>
            </Column>
            <Column field="error_message" :header="t('backups.error')">
              <template #body="{ data }">
                <template v-if="data.error_message">
                  <div style="font-size: 12px; color: var(--p-red-400)">{{ backupErrorTitle(data.error_message) }}</div>
                  <div v-if="backupErrorHint(data.error_message)" class="muted" style="font-size: 11px; margin-top: 2px">
                    {{ backupErrorHint(data.error_message) }}
                  </div>
                </template>
                <span v-else class="muted">—</span>
              </template>
            </Column>
            <Column header="" style="width: 200px">
              <template #body="{ data }">
                <div class="flex-row" style="gap: 6px">
                  <template v-if="data.status === 'running'">
                    <div class="history-running-cell">
                      <i class="fa-solid fa-spinner fa-spin" style="color: #ca8a04; font-size: 13px"></i>
                      <span class="history-running-stage">{{ data.stage || t('backups.inProgress') }}</span>
                      <Button
                        v-if="findActiveByTaskId(data.task_id)"
                        size="small" text severity="secondary"
                        @click="focusRunningTask(data.task_id)"
                        :title="t('backups.openInTaskPanel')"
                      >
                        <i class="fa-solid fa-up-right-from-square"></i>
                      </Button>
                      <template v-else>
                        <Button
                          size="small" severity="danger" outlined
                          :loading="abortingId === data.id"
                          @click="abortBackup(data)"
                          :title="t('backups.forceAbortHint')"
                        >
                          <i class="fa-solid fa-skull" style="margin-right: 4px"></i>{{ t('backups.abort') }}
                        </Button>
                      </template>
                    </div>
                  </template>
                  <template v-else>
                    <Button v-if="data.status === 'success' && data.file_path" size="small" severity="secondary" outlined :loading="downloadingId === data.id" @click="downloadBackup(data)" :title="t('backups.downloadDump')">
                      <i class="fa-solid fa-download"></i>
                    </Button>
                    <Button size="small" severity="danger" text @click="confirmDeleteOne(data)" :loading="deletingId === data.id" :title="t('common.delete')">
                      <i class="fa-solid fa-trash"></i>
                    </Button>
                  </template>
                </div>
              </template>
            </Column>
          </DataTable>
        </TabPanel>

        <!-- ───── Восстановление ───── -->
        <TabPanel value="restore">
          <div class="restore-layout">
            <!-- Левая колонка: список бэкапов -->
            <div class="restore-list-col">
              <div class="restore-list-filters">
                <Select
                  v-model="restoreServerFilter"
                  :options="[{ label: t('backups.allServers'), value: null }, ...serverOptions]"
                  option-label="label" option-value="value"
                  :placeholder="t('backups.allServers')"
                  style="width: 190px"
                />
                <InputText v-model="restoreDbSearch" :placeholder="t('backups.filterByDb')" style="width: 160px" />
              </div>
              <DataTable
                v-model:selection="restoreSelectedBackup"
                selection-mode="single"
                :value="restoreBackups"
                :loading="historyLoading"
                striped-rows
                scroll-height="460px"
                :scrollable="true"
                data-key="id"
                class="restore-table"
                @row-select="onRestoreBackupSelect"
              >
                <template #empty>
                  <div class="muted" style="padding: 20px; text-align: center">{{ t('backups.noSuccessfulBackups') }}</div>
                </template>
                <Column selection-mode="single" style="width: 36px" />
                <Column field="id" header="ID" style="width: 55px" sortable />
                <Column :header="t('common.server')" style="width: 90px">
                  <template #body="{ data }">
                    <span style="font-size: 12px">{{ serverName(data.server_id) }}</span>
                  </template>
                </Column>
                <Column field="database_name" :header="t('backups.db')" sortable />
                <Column field="backup_format" :header="t('backups.format')" style="width: 75px">
                  <template #body="{ data }">
                    <Tag severity="secondary" :value="data.backup_format || 'custom'" style="font-size: 11px" />
                  </template>
                </Column>
                <Column field="file_size" :header="t('backups.size')" style="width: 85px" sortable>
                  <template #body="{ data }">{{ data.file_size ? formatBytes(data.file_size) : '—' }}</template>
                </Column>
                <Column field="started_at" :header="t('backups.date')" style="width: 150px" sortable>
                  <template #body="{ data }">{{ formatDate(data.started_at) }}</template>
                </Column>
              </DataTable>
            </div>

            <!-- Правая колонка: конфигурация -->
            <div class="restore-config-col">
              <template v-if="restoreSelectedBackup">
                <!-- Карточка источника -->
                <div class="restore-source-card">
                  <div class="restore-card-title">
                    <i class="fa-solid fa-box-archive"></i> {{ t('backups.source') }}
                  </div>
                  <div class="restore-info-grid">
                    <span class="ri-label">{{ t('common.server') }}</span>
                    <span class="ri-value">{{ serverName(restoreSelectedBackup.server_id) }}</span>
                    <span class="ri-label">{{ t('common.database') }}</span>
                    <span class="ri-value"><strong>{{ restoreSelectedBackup.database_name }}</strong></span>
                    <span class="ri-label">{{ t('backups.date') }}</span>
                    <span class="ri-value">{{ formatDate(restoreSelectedBackup.started_at) }}</span>
                    <span class="ri-label">{{ t('backups.size') }}</span>
                    <span class="ri-value">{{ restoreSelectedBackup.file_size ? formatBytes(restoreSelectedBackup.file_size) : '—' }}</span>
                    <span class="ri-label">{{ t('backups.format') }}</span>
                    <span class="ri-value"><Tag severity="secondary" :value="restoreSelectedBackup.backup_format || 'custom'" style="font-size: 11px" /></span>
                    <template v-if="restoreSelectedBackup.checksum">
                      <span class="ri-label">MD5</span>
                      <span class="ri-value ri-mono">{{ restoreSelectedBackup.checksum }}</span>
                    </template>
                  </div>
                </div>

                <!-- Конфигурация цели -->
                <div class="restore-target-card">
                  <div class="restore-card-title">
                    <i class="fa-solid fa-server"></i> {{ t('backups.restoreTarget') }}
                  </div>
                  <div class="restore-field">
                    <label>{{ t('common.server') }}</label>
                    <Select
                      v-model="restoreTargetServerId"
                      :options="serverOptions"
                      option-label="label" option-value="value"
                      :placeholder="t('backups.selectServer')"
                      style="width: 100%"
                    />
                  </div>
                  <div class="restore-field">
                    <label>{{ t('common.database') }}</label>
                    <InputText
                      v-model="restoreTargetDb"
                      :placeholder="t('backups.targetDbPlaceholder')"
                      style="width: 100%"
                    />
                    <small class="restore-field-hint">{{ t('backups.targetDbHint') }}</small>
                  </div>
                </div>

                <!-- Предупреждения -->
                <div v-if="restoreCrossServer" class="restore-warning-box">
                  <i class="fa-solid fa-triangle-exclamation"></i>
                  {{ t('backups.restoreToPrefix') }} <strong>{{ t('backups.anotherServer') }}</strong>: {{ serverName(restoreTargetServerId!) }}
                </div>
                <div v-if="restoreCrossDb" class="restore-warning-box">
                  <i class="fa-solid fa-triangle-exclamation"></i>
                  {{ t('backups.targetDb') }} (<strong>{{ restoreTargetDb }}</strong>) {{ t('backups.differsFromSource') }}
                </div>
                <div v-if="restoreTargetIsProduction" class="restore-danger-box">
                  <i class="fa-solid fa-radiation"></i>
                  {{ t('backups.targetServerIs') }} <strong>PRODUCTION</strong>. {{ t('backups.dataWillBeOverwritten') }}
                </div>

                <Button
                  :disabled="!restoreTargetServerId || !restoreTargetDb.trim() || restoreLoading"
                  :loading="restoreLoading"
                  severity="danger"
                  style="width: 100%; margin-top: 12px"
                  @click="runRestore"
                >
                  <i class="fa-solid fa-arrow-rotate-left" style="margin-right: 8px"></i>
                  {{ t('backups.runRestore') }}
                </Button>
              </template>

              <div v-else class="restore-placeholder">
                <i class="fa-solid fa-hand-pointer restore-placeholder-icon"></i>
                <p style="margin: 12px 0 4px; font-size: 15px; font-weight: 500">{{ t('backups.selectBackup') }}</p>
                <p class="muted" style="font-size: 13px">{{ t('backups.selectBackupHint') }}</p>
              </div>
            </div>
          </div>
        </TabPanel>

        <TabPanel value="restore-history">
          <DataTable
            :value="restoreHistory"
            :loading="historyLoading"
            :paginator="restoreHistory.length > 25"
            :rows="25"
            striped-rows
            size="small"
          >
            <template #empty>
              <div style="padding: 24px; text-align: center; color: var(--p-text-muted-color)">
                {{ t('backups.noRestores') }}
              </div>
            </template>
            <Column :header="t('common.server')" style="width: 160px">
              <template #body="{ data }">{{ data.server_name || serverName(data.server_id) }}</template>
            </Column>
            <Column field="database_name" :header="t('common.database')" />
            <Column :header="t('common.status')" style="width: 120px">
              <template #body="{ data }"><Tag :severity="statusSeverity(data.status)" :value="data.status" /></template>
            </Column>
            <Column :header="t('backups.duration')" style="width: 80px">
              <template #body="{ data }">{{ data.duration_seconds != null ? t('backups.secondsShort', { n: data.duration_seconds }) : '—' }}</template>
            </Column>
            <Column field="started_at" :header="t('backups.startedAt')" style="width: 170px" sortable>
              <template #body="{ data }">{{ formatDate(data.started_at) }}</template>
            </Column>
            <Column field="error_message" :header="t('backups.error')">
              <template #body="{ data }">
                <span v-if="data.error_message" style="color: var(--p-red-400, #f87171); font-size: 12px">{{ data.error_message }}</span>
                <span v-else class="muted">—</span>
              </template>
            </Column>
          </DataTable>
        </TabPanel>

        <TabPanel value="schedules">
          <div class="flex-row tab-panel-toolbar">
            <Button @click="openScheduleModal" :disabled="!selectedServerId">
              <i class="fa-solid fa-plus" style="margin-right: 6px"></i>{{ t('backups.addSchedule') }}
            </Button>
          </div>
          <DataTable :value="schedules" striped-rows>
            <Column field="id" header="ID" style="width: 70px" />
            <Column field="server_id" :header="t('common.server')" style="width: 90px" />
            <Column field="database_name" :header="t('backups.db')" style="width: 140px" />
            <Column :header="t('backups.storages')" style="width: 180px">
              <template #body="{ data }">
                <span v-if="scheduleStorageLabel(data)" style="font-size: 12px">{{ scheduleStorageLabel(data) }}</span>
                <span v-else class="muted">{{ t('backups.default') }}</span>
              </template>
            </Column>
            <Column field="cron_expression" :header="t('backups.schedule')" style="width: 220px">
              <template #body="{ data }">
                <div class="flex-col" style="gap: 2px">
                  <span v-if="cronScheduleName(data.cron_expression)" style="font-size: 12px">{{ cronScheduleName(data.cron_expression) }}</span>
                  <code class="code-chip">{{ data.cron_expression }}</code>
                </div>
              </template>
            </Column>
            <Column field="retention_days" :header="t('backups.retention')" style="width: 110px">
              <template #body="{ data }">{{ t('backups.daysShort', { n: data.retention_days }) }}</template>
            </Column>
            <Column field="is_active" :header="t('backups.active')" style="width: 100px">
              <template #body="{ data }">
                <Tag :severity="data.is_active ? 'success' : 'secondary'" :value="data.is_active ? t('common.yes') : t('common.no')" />
              </template>
            </Column>
          </DataTable>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>

  <Dialog v-model:visible="showBackupDialog" modal :header="t('backups.createBackup')" :style="{ width: excludeTablesOpen ? '680px' : '440px' }">
    <div class="flex-col" style="gap: 16px; padding: 4px 0">
      <div class="flex-col" style="gap: 4px">
        <label style="font-size: 13px; color: var(--p-text-muted-color)">{{ t('common.database') }}</label>
        <span style="font-weight: 600; font-size: 15px">{{ backupTargetDb }}</span>
      </div>

      <div class="flex-col" style="gap: 8px">
        <label style="font-size: 13px; color: var(--p-text-muted-color)">{{ t('backups.storagesForUpload') }}</label>
        <MultiSelect
          v-model="backupSelectedStorages"
          :options="orgStorages"
          option-label="label"
          option-value="value"
          :placeholder="t('backups.selectStorages')"
          :loading="storagesLoading"
          display="chip"
          :max-selected-labels="3"
          style="width: 100%"
        />
        <span style="font-size: 12px; color: var(--p-text-muted-color)">
          {{ t('backups.storagesHint') }}
        </span>
      </div>

      <div class="flex-col" style="gap: 8px">
        <label style="font-size: 13px; color: var(--p-text-muted-color)">{{ t('backups.dumpFormat') }}</label>
        <div class="format-options">
          <div
            v-for="f in backupFormats"
            :key="f.value"
            class="format-option"
            :style="formatOptionStyle(f.value)"
            @click="backupFormat = f.value"
          >
            <div class="format-option-header">
              <i :class="f.icon" :style="{ fontSize: '16px', color: backupFormat === f.value ? (isDark ? '#34d399' : '#059669') : '' }"></i>
              <span class="format-option-name" :style="{ color: isDark ? '#e2e8f0' : '#1e293b' }">{{ f.label }}</span>
              <span v-if="f.ext" class="format-option-ext" :style="isDark ? { background: '#243047', color: '#94a3b8' } : {}">{{ f.ext }}</span>
            </div>
            <div class="format-option-desc" :style="{ color: isDark ? '#94a3b8' : '#64748b' }">{{ f.desc }}</div>
          </div>
        </div>
      </div>

      <!-- Исключение таблиц -->
      <div class="exclude-section" :class="{ open: excludeTablesOpen }">
        <div class="exclude-toggle" @click="toggleExcludeTables">
          <div style="display: flex; align-items: center; gap: 8px">
            <i class="fa-solid fa-table" style="font-size: 13px; color: var(--p-text-muted-color)"></i>
            <span style="font-size: 13px; font-weight: 600">{{ t('backups.excludeTables') }}</span>
            <span v-if="excludedTables.length > 0" class="exclude-badge">{{ excludedTables.length }}</span>
          </div>
          <i :class="excludeTablesOpen ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'" style="font-size: 11px; color: var(--p-text-muted-color)"></i>
        </div>

        <div v-if="excludeTablesOpen" class="exclude-body">
          <div v-if="tablesLoading" style="padding: 20px; text-align: center; color: var(--p-text-muted-color); font-size: 13px">
            <i class="fa-solid fa-spinner fa-spin" style="margin-right: 6px"></i>{{ t('backups.loadingTables') }}
          </div>
          <template v-else>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px">
              <span style="font-size: 12px; color: var(--p-text-muted-color)">{{ t('backups.tablesCount', { count: tablesSizeList.length }) }} · {{ t('backups.sortedBySize') }}</span>
              <div style="flex: 1"></div>
              <Button v-if="excludedTables.length > 0" text size="small" severity="secondary" @click="excludedTables = []" style="font-size: 12px; padding: 2px 8px">{{ t('backups.reset') }}</Button>
            </div>
            <div class="tables-list">
              <div
                v-for="t in tablesSizeList"
                :key="t.schema + '.' + t.tablename"
                class="table-row"
                :class="{ excluded: excludedTables.includes(t.schema + '.' + t.tablename) }"
                @click="toggleExcludeTable(t.schema + '.' + t.tablename)"
              >
                <input
                  type="checkbox"
                  :checked="excludedTables.includes(t.schema + '.' + t.tablename)"
                  @click.stop="toggleExcludeTable(t.schema + '.' + t.tablename)"
                  style="flex-shrink: 0; cursor: pointer; width: 14px; height: 14px"
                />
                <div class="table-name-col">
                  <span class="table-schema">{{ t.schema }}</span><span class="table-dot">.</span><span class="table-name">{{ t.tablename }}</span>
                </div>
                <div class="table-size-bar-wrap">
                  <div class="table-size-bar" :style="{ width: tableSizePercent(t.total_bytes) + '%' }"></div>
                </div>
                <span class="table-size-text">{{ t.total_size }}</span>
                <span class="table-rows-text">{{ formatRows(t.row_estimate) }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
    <template #footer>
      <Button text @click="showBackupDialog = false">{{ t('common.cancel') }}</Button>
      <Button :loading="backupStarting" @click="startBackup">
        <i class="fa-solid fa-box-archive" style="margin-right: 6px"></i>{{ t('common.run') }}
        <span v-if="excludedTables.length > 0" style="margin-left: 4px; opacity: 0.7; font-size: 12px">(−{{ t('backups.tablesShort', { count: excludedTables.length }) }})</span>
      </Button>
    </template>
  </Dialog>

  <Dialog v-model:visible="showDeleteConfirm" modal :header="deleteConfirmHeader" :style="{ width: '420px' }">
    <div style="display: flex; align-items: flex-start; gap: 14px; padding: 8px 0">
      <i class="fa-solid fa-triangle-exclamation" style="font-size: 24px; color: var(--p-red-500); flex-shrink: 0; margin-top: 2px"></i>
      <div>
        <div style="font-size: 14px; margin-bottom: 6px">{{ deleteConfirmText }}</div>
        <div style="font-size: 12px; color: var(--p-text-muted-color)">{{ t('backups.deleteWarning') }}</div>
      </div>
    </div>
    <template #footer>
      <Button text @click="showDeleteConfirm = false">{{ t('common.cancel') }}</Button>
      <Button severity="danger" :loading="deleteLoading" @click="executeDelete">{{ t('common.delete') }}</Button>
    </template>
  </Dialog>

  <Dialog v-model:visible="showSchedule" modal :header="t('backups.addSchedule')" :style="{ width: '500px' }">
    <div class="flex-col" style="gap: 14px">
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('common.server') }}</label>
        <span style="font-weight: 500">{{ selectedServerName }}</span>
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('common.database') }}</label>
        <Select v-model="scheduleForm.database_name" :options="dbOptions" option-label="label" option-value="value" :placeholder="t('backups.selectDb')" filter />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('backups.storagesForUpload') }}</label>
        <MultiSelect
          v-model="scheduleSelectedStorages"
          :options="orgStorages"
          option-label="label"
          option-value="value"
          :placeholder="t('backups.selectStorages')"
          :loading="storagesLoading"
          display="chip"
          :max-selected-labels="3"
          style="width: 100%"
        />
        <span style="font-size: 12px; color: var(--p-text-muted-color)">
          {{ t('backups.scheduleStoragesHint') }}
        </span>
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('backups.schedule') }}</label>
        <Select
          v-model="scheduleForm.schedule_id"
          :options="[...cronSchedules, { id: -1, name: t('backups.customSchedule'), cron_expression: '', description: '' }]"
          option-label="name"
          option-value="id"
          :placeholder="t('backups.selectFromCatalog')"
          filter
          :loading="cronSchedulesLoading"
          @change="onBackupScheduleChange"
        >
          <template #option="{ option }">
            <div style="display: flex; align-items: center; gap: 10px; width: 100%">
              <span style="flex: 1">{{ option.name }}</span>
              <code v-if="option.cron_expression" style="font-size: 11px; color: var(--p-text-muted-color)">{{ option.cron_expression }}</code>
            </div>
          </template>
        </Select>
        <CronInput
          v-if="scheduleForm.schedule_id === -1"
          v-model="scheduleForm.cron_expression"
          style="margin-top: 6px"
        />
        <div v-if="activeScheduleCron && scheduleForm.schedule_id !== -1" class="schedule-cron-preview">
          <i class="fa-solid fa-circle-info"></i>
          {{ cronSchedulePreview(activeScheduleCron) }}
        </div>
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('backups.retentionDays') }}</label>
        <InputNumber v-model="scheduleForm.retention_days" :min="1" />
      </div>
    </div>
    <template #footer>
      <Button text @click="showSchedule = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submittingSchedule" @click="submitSchedule(addSchedule)" :disabled="!scheduleForm.database_name || scheduleSelectedStorages.length === 0 || !resolvedScheduleCron || submittingSchedule">{{ t('backups.create') }}</Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import PageHeader from '../components/ui/PageHeader.vue'
import AlertBanner from '../components/ui/AlertBanner.vue'
import AiInsight from '../components/AiInsight.vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import CronInput from '../components/CronInput.vue'
import api from '../api/client'
import type { Server, Database, BackupHistory, BackupSchedule } from '../api/types'
import { useTasksStore } from '../stores/tasks'
import { useThemeStore } from '../stores/theme'
import { useHealthStore } from '../stores/health'
import { classifyPgError } from '../utils/pgHealth'
import { useSubmitting } from '../composables/useSubmitting'

function backupErrorTitle(msg: string): string {
  return classifyPgError(msg).title
}

function backupErrorHint(msg: string): string {
  const h = classifyPgError(msg)
  return h.code === 'generic' ? '' : h.hint
}

const { t } = useI18n()
const toast = useToast()
const tasksStore = useTasksStore()
const themeStore = useThemeStore()
const healthStore = useHealthStore()
const isDark = computed(() => themeStore.mode === 'dark')
// In-flight guard против двойного клика по кнопке создания расписания
const { submitting: submittingSchedule, submit: submitSchedule } = useSubmitting()

const servers = ref<Server[]>([])
const serversLoading = ref(false)
const selectedServerId = ref<number | null>(null)

const serverOptions = computed(() =>
  servers.value.map(s => ({ label: `${s.name} (${s.host}:${s.port})`, value: s.id }))
)
const selectedServerName = computed(() => {
  const s = servers.value.find(s => s.id === selectedServerId.value)
  return s ? `${s.name} (${s.host})` : '—'
})
const selectedServer = computed(() =>
  servers.value.find(s => s.id === selectedServerId.value) ?? null
)

async function loadServers() {
  serversLoading.value = true
  try {
    const { data } = await api.get<Server[]>('/servers')
    servers.value = data
  } finally { serversLoading.value = false }
}

const databases = ref<Database[]>([])
const dbsLoading = ref(false)
const SYSTEM_DBS = new Set(['postgres', 'template0', 'template1'])
const userDatabases = computed(() => databases.value.filter(d => !SYSTEM_DBS.has(d.datname)))
const dbOptions = computed(() => userDatabases.value.map(d => ({ label: `${d.datname} (${d.size})`, value: d.datname })))

async function loadDatabases(serverId: number) {
  dbsLoading.value = true
  try {
    const { data } = await api.get<Database[]>(`/servers/${serverId}/databases`)
    databases.value = data
  } catch { databases.value = [] }
  finally { dbsLoading.value = false }
}

watch(selectedServerId, (id) => { if (id) loadDatabases(id); else databases.value = [] })

interface RestoreHistoryRow {
  id: number
  server_id: number
  server_name: string | null
  database_name: string
  status: string
  backup_format: string | null
  duration_seconds: number | null
  error_message: string | null
  started_at: string
  finished_at: string | null
}

const history = ref<BackupHistory[]>([])
const restoreHistory = ref<RestoreHistoryRow[]>([])
const schedules = ref<BackupSchedule[]>([])
const historyLoading = ref(false)
const historyServerFilter = ref<number | null>(null)
const selectedRows = ref<BackupHistory[]>([])
const deleteLoading = ref(false)
const deletingId = ref<number | null>(null)
const abortingId = ref<number | null>(null)
const showDeleteConfirm = ref(false)
const deleteConfirmHeader = ref('')
const deleteConfirmText = ref('')
let pendingDeleteIds: number[] = []

function confirmDeleteOne(row: BackupHistory) {
  pendingDeleteIds = [row.id]
  deleteConfirmHeader.value = t('backups.deleteBackup')
  deleteConfirmText.value = t('backups.deleteRecordConfirm', { id: row.id, db: row.database_name, date: formatDate(row.started_at) })
  showDeleteConfirm.value = true
}

function confirmDeleteSelected() {
  pendingDeleteIds = selectedRows.value.map(r => r.id)
  deleteConfirmHeader.value = t('backups.deleteSelectedBackups')
  deleteConfirmText.value = t('backups.deleteCountConfirm', { count: pendingDeleteIds.length })
  showDeleteConfirm.value = true
}

async function executeDelete() {
  deleteLoading.value = true
  if (pendingDeleteIds.length === 1) deletingId.value = pendingDeleteIds[0]
  try {
    if (pendingDeleteIds.length === 1) {
      await api.delete(`/backups/history/${pendingDeleteIds[0]}`)
    } else {
      await api.delete('/backups/history', { data: { ids: pendingDeleteIds } })
    }
    history.value = history.value.filter(h => !pendingDeleteIds.includes(h.id))
    selectedRows.value = selectedRows.value.filter(r => !pendingDeleteIds.includes(r.id))
    toast.add({ severity: 'success', summary: t('backups.deleted'), life: 2000 })
    showDeleteConfirm.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('backups.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    deleteLoading.value = false
    deletingId.value = null
    pendingDeleteIds = []
  }
}
const filteredHistory = computed(() =>
  !historyServerFilter.value ? history.value : history.value.filter(h => h.server_id === historyServerFilter.value)
)

function lastBackupFor(dbName: string): BackupHistory | undefined {
  return history.value.find(h => h.server_id === selectedServerId.value && h.database_name === dbName)
}

function activeTaskFor(dbName: string) {
  if (!selectedServerId.value) return undefined
  return tasksStore.findActive(selectedServerId.value, dbName)
}

function openTaskProgress(dbName: string) {
  const t = activeTaskFor(dbName)
  if (t) tasksStore.focusTask(t.taskId)
}

async function abortBackup(row: BackupHistory) {
  abortingId.value = row.id
  try {
    await api.post(`/backups/history/${row.id}/abort`)
    history.value = history.value.map(h =>
      h.id === row.id ? { ...h, status: 'failed', stage: 'aborted', error_message: t('backups.forceAborted') } : h
    )
    toast.add({ severity: 'warn', summary: t('backups.aborted'), detail: t('backups.abortedDetail', { id: row.id }), life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('backups.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    abortingId.value = null
  }
}

function findActiveByTaskId(taskId: string | null | undefined) {
  if (!taskId) return undefined
  return tasksStore.tasks.find(t => t.taskId === taskId && !t.done && !t.failed)
}

function focusRunningTask(taskId: string | null | undefined) {
  if (!taskId) return
  const t = findActiveByTaskId(taskId)
  if (t) tasksStore.focusTask(t.taskId)
}

const showBackupDialog = ref(false)
const backupTargetDb = ref('')
const backupFormat = ref('custom')
const backupStarting = ref(false)
const backupSelectedStorages = ref<number[]>([])

interface OrgStorageOption {
  id: number
  name: string
  bucket: string
  api_type: string
}

const orgStorageRows = ref<OrgStorageOption[]>([])
const storagesLoading = ref(false)
const orgStorages = computed(() =>
  orgStorageRows.value.map(s => ({
    label: `${s.name} (${s.bucket})`,
    value: s.id,
  }))
)

async function loadOrgStorages() {
  storagesLoading.value = true
  try {
    const { data } = await api.get<OrgStorageOption[]>('/s3-storages')
    orgStorageRows.value = data
  } catch {
    orgStorageRows.value = []
  } finally {
    storagesLoading.value = false
  }
}

const backupFormats = computed(() => [
  {
    value: 'custom',
    label: 'Custom',
    ext: '.dump',
    icon: 'fa-solid fa-cube',
    desc: t('backups.formatCustomDesc'),
  },
  {
    value: 'plain',
    label: 'Plain SQL',
    ext: '.sql',
    icon: 'fa-solid fa-file-code',
    desc: t('backups.formatPlainDesc'),
  },
  {
    value: 'tar',
    label: 'Tar',
    ext: '.tar',
    icon: 'fa-solid fa-file-zipper',
    desc: t('backups.formatTarDesc'),
  },
])

function formatOptionStyle(value: string): Record<string, string> {
  const selected = backupFormat.value === value
  if (isDark.value) {
    return {
      border: selected ? '2px solid #34d399' : '2px solid #2d3f57',
      background: selected ? 'rgba(52,211,153,0.10)' : '#1c2a3f',
      borderRadius: '8px',
      padding: '10px 14px',
      cursor: 'pointer',
    }
  }
  return {
    border: selected ? '2px solid #10b981' : '2px solid #e2e8f0',
    background: selected ? 'rgba(16,185,129,0.06)' : '#f8fafc',
    borderRadius: '8px',
    padding: '10px 14px',
    cursor: 'pointer',
  }
}

const excludeTablesOpen = ref(false)
const excludedTables = ref<string[]>([])
const tablesLoading = ref(false)
const tablesSizeList = ref<{ schema: string; tablename: string; total_bytes: number; total_size: string; data_size: string; index_size: string; row_estimate: number }[]>([])

function tableSizePercent(bytes: number): number {
  const max = tablesSizeList.value[0]?.total_bytes || 1
  return Math.max(2, Math.round((bytes / max) * 100))
}

function formatRows(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

function toggleExcludeTable(key: string) {
  const idx = excludedTables.value.indexOf(key)
  if (idx >= 0) excludedTables.value.splice(idx, 1)
  else excludedTables.value.push(key)
}

async function toggleExcludeTables() {
  excludeTablesOpen.value = !excludeTablesOpen.value
  if (excludeTablesOpen.value && tablesSizeList.value.length === 0) {
    await loadTablesSizes()
  }
}

async function loadTablesSizes() {
  if (!selectedServerId.value || !backupTargetDb.value) return
  tablesLoading.value = true
  try {
    const { data } = await api.get(`/servers/${selectedServerId.value}/databases/${backupTargetDb.value}/tables-size`)
    tablesSizeList.value = data
  } catch {
    tablesSizeList.value = []
  } finally {
    tablesLoading.value = false
  }
}

function openBackupDialog(dbName: string) {
  backupTargetDb.value = dbName
  backupFormat.value = 'custom'
  excludeTablesOpen.value = false
  excludedTables.value = []
  tablesSizeList.value = []
  const server = servers.value.find(s => s.id === selectedServerId.value)
  backupSelectedStorages.value = server?.storage_id ? [server.storage_id] : []
  showBackupDialog.value = true
  if (orgStorageRows.value.length === 0) void loadOrgStorages()
}

async function startBackup() {
  if (backupStarting.value) return
  if (!selectedServerId.value) return
  const server = servers.value.find(s => s.id === selectedServerId.value)
  if (backupSelectedStorages.value.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('backups.noStorageSelected'),
      detail: t('backups.selectAtLeastOneStorageBackup'),
      life: 5000,
    })
    return
  }
  backupStarting.value = true
  try {
    const { data } = await api.post('/backups/run', {
      server_id: selectedServerId.value,
      database_name: backupTargetDb.value,
      backup_format: backupFormat.value,
      excluded_tables: excludedTables.value,
      storage_ids: backupSelectedStorages.value,
    })
    tasksStore.seedBackupTask(data.task_id, {
      serverId: selectedServerId.value,
      serverName: server?.name || `Server #${selectedServerId.value}`,
      database: backupTargetDb.value,
      backupFormat: backupFormat.value,
      hasStorage: backupSelectedStorages.value.length > 0,
    })
    tasksStore.focusTask(data.task_id)
    toast.add({ severity: 'success', summary: t('backups.queued'), detail: `${backupTargetDb.value}: ${data.task_id.slice(0, 8)}…`, life: 3000 })
    showBackupDialog.value = false
    void fetchHistory()
    void tasksStore.syncRunningTasks()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('backups.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    backupStarting.value = false
  }
}

const downloadingId = ref<number | null>(null)

async function downloadBackup(b: BackupHistory) {
  downloadingId.value = b.id
  try {
    // Бэкенд стримит файл напрямую из MinIO — без внутренних Docker-адресов
    const token = localStorage.getItem('access_token')
    const resp = await fetch(`/api/backups/history/${b.id}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    const blob = await resp.blob()
    const disposition = resp.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="?([^"]+)"?/)
    const filename = match?.[1] || `backup_${b.id}.dump`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('backups.error'), detail: e.message || t('backups.downloadFailed'), life: 4000 })
  } finally {
    downloadingId.value = null
  }
}

// ─── Restore panel ────────────────────────────────────────────────
const restoreServerFilter = ref<number | null>(null)
const restoreDbSearch = ref('')
const restoreSelectedBackup = ref<BackupHistory | null>(null)
const restoreTargetServerId = ref<number | null>(null)
const restoreTargetDb = ref('')
const restoreLoading = ref(false)

const restoreBackups = computed(() =>
  history.value.filter(b => {
    if (b.status !== 'success' || !b.file_path) return false
    if (restoreServerFilter.value !== null && b.server_id !== restoreServerFilter.value) return false
    if (restoreDbSearch.value && !b.database_name.toLowerCase().includes(restoreDbSearch.value.toLowerCase())) return false
    return true
  })
)

const restoreCrossServer = computed(() =>
  restoreSelectedBackup.value !== null &&
  restoreTargetServerId.value !== null &&
  restoreTargetServerId.value !== restoreSelectedBackup.value.server_id
)

const restoreCrossDb = computed(() =>
  restoreSelectedBackup.value !== null &&
  restoreTargetDb.value.trim() !== '' &&
  restoreTargetDb.value.trim() !== restoreSelectedBackup.value.database_name
)

const restoreTargetIsProduction = computed(() => {
  if (!restoreTargetServerId.value) return false
  const s = servers.value.find(s => s.id === restoreTargetServerId.value)
  return s?.environment === 'production'
})

function serverName(id: number): string {
  const s = servers.value.find(s => s.id === id)
  return s ? s.name : `#${id}`
}

function onRestoreBackupSelect(event: any) {
  const b: BackupHistory = event.data
  restoreTargetServerId.value = b.server_id
  restoreTargetDb.value = b.database_name
}

async function runRestore() {
  if (restoreLoading.value) return
  if (!restoreSelectedBackup.value || !restoreTargetServerId.value || !restoreTargetDb.value.trim()) return
  restoreLoading.value = true
  try {
    const { data } = await api.post('/backups/restore', {
      server_id: restoreTargetServerId.value,
      database_name: restoreTargetDb.value.trim(),
      backup_id: restoreSelectedBackup.value.id,
    })
    toast.add({
      severity: 'success',
      summary: t('backups.restoreStarted'),
      detail: `${restoreTargetDb.value} ← #${restoreSelectedBackup.value.id} (${data.task_id.slice(0, 8)}…)`,
      life: 4000,
    })
    restoreSelectedBackup.value = null
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('backups.error'), detail: e.response?.data?.detail || t('backups.restoreStartFailed'), life: 5000 })
  } finally {
    restoreLoading.value = false
  }
}

const showSchedule = ref(false)
const scheduleForm = reactive({
  server_id: 0,
  database_name: '',
  schedule_id: 0 as number,
  cron_expression: '',
  retention_days: 30,
})
const scheduleSelectedStorages = ref<number[]>([])

interface CronScheduleOption {
  id: number
  name: string
  cron_expression: string
  description?: string | null
}

const cronSchedules = ref<CronScheduleOption[]>([])
const cronSchedulesLoading = ref(false)

const activeScheduleCron = computed(() => {
  if (scheduleForm.schedule_id === -1) return scheduleForm.cron_expression
  return cronSchedules.value.find(s => s.id === scheduleForm.schedule_id)?.cron_expression ?? ''
})

const resolvedScheduleCron = computed(() => activeScheduleCron.value.trim())

async function loadCronSchedules() {
  cronSchedulesLoading.value = true
  try {
    const { data } = await api.get<CronScheduleOption[]>('/cron-schedules')
    cronSchedules.value = data
  } catch {
    cronSchedules.value = []
  } finally {
    cronSchedulesLoading.value = false
  }
}

function defaultCronScheduleId(): number {
  const preferred = cronSchedules.value.find(s => s.cron_expression === '0 2 * * *')
  if (preferred) return preferred.id
  return cronSchedules.value[0]?.id ?? -1
}

function onBackupScheduleChange() {
  if (scheduleForm.schedule_id !== -1) scheduleForm.cron_expression = ''
}

function cronScheduleName(expr: string): string {
  return cronSchedules.value.find(s => s.cron_expression === expr)?.name ?? ''
}

function cronSchedulePreview(expr: string): string {
  const known = cronSchedules.value.find(s => s.cron_expression === expr)
  if (known?.description) return known.description
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return t('backups.invalidCron')
  const [min, hour, dom, month, dow] = parts
  if (dom === '*' && month === '*' && dow === '*') {
    if (min !== '*' && hour !== '*') return t('backups.everyDayAt', { time: `${hour.padStart(2, '0')}:${min.padStart(2, '0')}` })
    if (min === '0' && hour === '*') return t('backups.everyHour')
  }
  if (hour.startsWith('*/')) return t('backups.everyNHours', { n: hour.slice(2) })
  return `cron: ${expr}`
}

function presetScheduleCron() {
  scheduleForm.schedule_id = defaultCronScheduleId()
  scheduleForm.cron_expression = ''
}

function scheduleStorageLabel(schedule: BackupSchedule): string {
  const ids = schedule.storage_ids || []
  if (ids.length === 0) return ''
  return ids
    .map(id => orgStorageRows.value.find(s => s.id === id)?.name || `#${id}`)
    .join(', ')
}

function presetScheduleStorages() {
  const server = servers.value.find(s => s.id === selectedServerId.value)
  scheduleSelectedStorages.value = server?.storage_id ? [server.storage_id] : []
}

function openScheduleModal() {
  scheduleForm.server_id = selectedServerId.value!
  scheduleForm.database_name = ''
  presetScheduleStorages()
  presetScheduleCron()
  showSchedule.value = true
  if (orgStorageRows.value.length === 0) void loadOrgStorages()
  if (cronSchedules.value.length === 0) void loadCronSchedules()
}

function openScheduleForDb(dbName: string) {
  scheduleForm.server_id = selectedServerId.value!
  scheduleForm.database_name = dbName
  presetScheduleStorages()
  presetScheduleCron()
  showSchedule.value = true
  if (orgStorageRows.value.length === 0) void loadOrgStorages()
  if (cronSchedules.value.length === 0) void loadCronSchedules()
}

async function addSchedule() {
  if (scheduleSelectedStorages.value.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('backups.noStorageSelected'),
      detail: t('backups.selectAtLeastOneStorage'),
      life: 4000,
    })
    return
  }
  const cronExpression = resolvedScheduleCron.value
  if (!cronExpression) {
    toast.add({
      severity: 'warn',
      summary: t('backups.noScheduleSelected'),
      detail: t('backups.selectScheduleHint'),
      life: 4000,
    })
    return
  }
  try {
    await api.post('/backups/schedules', {
      server_id: scheduleForm.server_id,
      database_name: scheduleForm.database_name,
      cron_expression: cronExpression,
      retention_days: scheduleForm.retention_days,
      storage_ids: scheduleSelectedStorages.value,
    })
    toast.add({ severity: 'success', summary: t('backups.scheduleCreated'), life: 2500 })
    showSchedule.value = false
    fetchHistory()
  } catch (e: any) { toast.add({ severity: 'error', summary: t('backups.error'), detail: e.response?.data?.detail || 'Error', life: 4000 }) }
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    const [h, s, rh] = await Promise.all([
      api.get('/backups/history'),
      api.get('/backups/schedules'),
      api.get('/backups/restore-history'),
    ])
    history.value = h.data
    schedules.value = s.data
    restoreHistory.value = rh.data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('backups.historyTab'),
      detail: e.response?.data?.detail || t('backups.historyLoadFailed'), life: 4000 })
  } finally { historyLoading.value = false }
}

function statusSeverity(s: string): 'success' | 'danger' | 'warn' | 'secondary' {
  const map: Record<string, 'success' | 'danger' | 'warn' | 'secondary'> = {
    success: 'success', failed: 'danger', running: 'warn',
  }
  return map[s] ?? 'secondary'
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDate(iso: string): string {
  try {
    // Бэкенд отдаёт UTC без суффикса — добавляем Z чтобы браузер корректно конвертировал в локальное время
    const utc = iso && !iso.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(iso) ? iso + 'Z' : iso
    return new Date(utc).toLocaleString('ru-RU')
  } catch { return iso }
}

function reloadAll() { loadServers(); fetchHistory() }

watch(
  () => tasksStore.tasks.map(t => `${t.taskId}:${t.done}:${t.failed}`).join(','),
  (curr, prev) => {
    if (prev && prev !== curr) fetchHistory()
  }
)

onMounted(() => { loadServers(); loadOrgStorages(); loadCronSchedules(); fetchHistory() })
</script>

<style scoped>
.spacer { flex: 1; min-width: 0; }

.schedule-cron-preview {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.format-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.format-option { transition: border-color 0.15s, background 0.15s; }
.format-option-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.format-option-name { font-weight: 600; font-size: 13px; }
.format-option-ext {
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 11px;
  background: var(--p-surface-200);
  color: var(--p-text-muted-color);
  padding: 1px 6px;
  border-radius: 4px;
}
.format-option-desc { font-size: 12px; }

.running-cell {
  gap: 10px;
  align-items: center;
  padding: 6px 10px;
  background: var(--p-yellow-50);
  border: 1px solid var(--p-yellow-200);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.running-cell:hover {
  background: var(--p-yellow-100);
}
:global(.app-dark) .running-cell {
  background: rgba(234, 179, 8, 0.08);
  border-color: rgba(234, 179, 8, 0.3);
}
:global(.app-dark) .running-cell:hover {
  background: rgba(234, 179, 8, 0.15);
}
.running-icon { color: var(--p-yellow-600); }
.running-text {
  font-size: 12px;
  color: var(--p-yellow-700);
  font-weight: 600;
}
:global(.app-dark) .running-text { color: var(--p-yellow-400); }
.running-pct {
  font-family: ui-monospace, 'Cascadia Code', 'SF Mono', Consolas, monospace;
  font-size: 12px;
  color: var(--p-text-color);
  margin-left: auto;
}
.running-cell-detached {
  opacity: 0.75;
  cursor: default;
}
.running-hint {
  font-size: 11px;
  color: var(--p-text-muted-color);
  margin-left: auto;
}
.history-running-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.history-running-stage {
  font-size: 12px;
  color: #ca8a04;
  font-weight: 600;
}
.history-running-hint {
  font-size: 11px;
  color: var(--p-text-muted-color);
}

/* ─── Exclude tables section ─── */
.exclude-section {
  border: 1px solid var(--p-surface-200);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.15s;
}
:global(.app-dark) .exclude-section { border-color: #2d3f57; }
.exclude-section.open { border-color: var(--p-primary-300); }
:global(.app-dark) .exclude-section.open { border-color: #3b82f6; }

.exclude-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  background: var(--p-surface-50);
  transition: background 0.15s;
}
.exclude-toggle:hover { background: var(--p-surface-100); }
:global(.app-dark) .exclude-toggle { background: #1c2a3f; }
:global(.app-dark) .exclude-toggle:hover { background: #243047; }

.exclude-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--p-red-500);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  min-width: 18px;
  height: 18px;
  border-radius: 9px;
  padding: 0 5px;
}

.exclude-body {
  padding: 10px 14px 12px;
  border-top: 1px solid var(--p-surface-200);
}
:global(.app-dark) .exclude-body { border-top-color: #2d3f57; }

.tables-list {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.table-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 12px;
}
.table-row:hover { background: var(--p-surface-100); }
:global(.app-dark) .table-row:hover { background: #243047; }
.table-row.excluded { background: rgba(239, 68, 68, 0.07); }
:global(.app-dark) .table-row.excluded { background: rgba(239, 68, 68, 0.12); }

.table-name-col {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.table-schema { color: var(--p-text-muted-color); font-size: 11px; }
.table-dot { color: var(--p-text-muted-color); }
.table-name { font-weight: 600; }

.table-size-bar-wrap {
  width: 80px;
  height: 4px;
  background: var(--p-surface-200);
  border-radius: 2px;
  flex-shrink: 0;
  overflow: hidden;
}
:global(.app-dark) .table-size-bar-wrap { background: #2d3f57; }
.table-size-bar {
  height: 100%;
  background: var(--p-primary-400);
  border-radius: 2px;
  transition: width 0.3s;
}

.table-size-text {
  width: 64px;
  text-align: right;
  flex-shrink: 0;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 11px;
  color: var(--p-text-muted-color);
}
.table-rows-text {
  width: 44px;
  text-align: right;
  flex-shrink: 0;
  font-size: 11px;
  color: var(--p-text-muted-color);
}

/* ── Restore panel ── */
.restore-layout {
  display: flex;
  gap: 20px;
  min-height: 520px;
  align-items: flex-start;
}
.restore-list-col {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.restore-list-filters {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.restore-config-col {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.restore-source-card,
.restore-target-card {
  border: 1px solid var(--p-surface-200);
  border-radius: 10px;
  padding: 14px 16px;
  background: var(--p-surface-50);
}
.app-dark .restore-source-card,
.app-dark .restore-target-card {
  border-color: #2d3f57;
  background: #1c2a3f;
}
.restore-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 7px;
}
.restore-info-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 12px;
  align-items: start;
  font-size: 13px;
}
.ri-label {
  color: var(--p-text-muted-color);
  white-space: nowrap;
}
.ri-value {
  word-break: break-all;
}
.ri-mono {
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 11px;
  word-break: break-all;
}
.restore-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;
}
.restore-field:last-child { margin-bottom: 0; }
.restore-field label {
  font-size: 12px;
  font-weight: 600;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.restore-field-hint {
  font-size: 11px;
  color: var(--p-text-muted-color);
}
.restore-warning-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.35);
  color: #a16207;
}
.app-dark .restore-warning-box { color: #fbbf24; }
.restore-danger-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #dc2626;
}
.restore-warning-box i, .restore-danger-box i { flex-shrink: 0; margin-top: 2px; }
.restore-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  height: 280px;
  border: 2px dashed var(--p-surface-300);
  border-radius: 12px;
  color: var(--p-text-muted-color);
  padding: 24px;
}
.app-dark .restore-placeholder { border-color: #2d3f57; }
.restore-placeholder-icon {
  font-size: 36px;
  opacity: 0.4;
}
</style>
