export interface AuthUser {
  id: number
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

export interface Server {
  id: number
  name: string
  host: string
  port: number
  environment: string
  admin_user: string
  ssh_user: string | null
  is_active: boolean
  pg_major_version: number | null
  organization_id: number | null
  organization_name?: string | null
  storage_id: number | null
  storage_name?: string | null
  health_status: string
  health_error: string | null
  health_error_code: string | null
  health_error_title: string | null
  health_error_hint: string | null
  health_fail_count: number
  health_checked_at: string | null
  created_at: string
  updated_at: string
}

export interface Role {
  rolname: string
  rolcanlogin: boolean
  rolsuper: boolean
  rolinherit: boolean
  rolcreatedb: boolean
  rolcreaterole: boolean
  rolconnlimit: number
  member_of: string[]
}

export interface Database {
  datname: string
  owner: string
  size: string
  size_bytes: number
  datacl: string | null
  encoding: string
}

export interface BackupHistory {
  id: number
  server_id: number
  database_name: string
  status: string
  stage: string | null
  task_id: string | null
  backup_format: string | null
  file_path: string | null
  storage_id: number | null
  storage_name: string | null
  file_size: number | null
  checksum: string | null
  duration_seconds: number | null
  error_message: string | null
  started_at: string
  finished_at: string | null
}

export interface BackupSchedule {
  id: number
  server_id: number
  database_name: string
  cron_expression: string
  retention_days: number
  storage_ids: number[] | null
  is_active: boolean
  created_at: string
}

export interface ConnectionStats {
  total: number
  active: number
  idle: number
  waiting: number
  max_connections?: number
}

export interface SlowQueriesMeta {
  available: boolean
  error: string | null
  hint: string | null
}

export interface MonitoringSnapshot {
  connections: ConnectionStats
  cache_hit_ratio: number | null
  database_sizes: { datname: string; size: string; size_bytes: number }[]
  storage?: {
    total_db_bytes: number
    tablespaces: { name: string; size_bytes: number }[]
  } | null
  slow_queries: { query: string; database?: string | null; calls: number; mean_time_ms: number; total_time_ms: number }[]
  slow_queries_meta: SlowQueriesMeta
  locks: { pid: number; relation: string | null; mode: string; granted: boolean; query: string | null; wait_duration?: string | null }[]
  collected_at?: string | null
  source?: 'redis' | 'live' | string | null
}

export interface DiagnosticCheck {
  name: string
  status: string
  details: string | null
}

export interface DiagnosticReport {
  server_name: string
  checks: DiagnosticCheck[]
  warnings: number
  ok: number
}

export interface PgSetting {
  name: string
  setting: string | null
  unit: string | null
  category: string | null
  context: string | null
  source: string | null
  sourcefile: string | null
  sourceline: number | null
  pending_restart: boolean | null
}

export interface PgFileSetting {
  sourcefile: string | null
  sourceline: number | null
  seqno: number | null
  name: string
  setting: string | null
  applied: boolean
  error: string | null
}

export interface PgHbaRule {
  rule_number: number | null
  file_name: string | null
  line_number: number | null
  type: string
  databases: string
  users: string
  address: string | null
  netmask: string | null
  auth_method: string | null
  options: string | null
  error: string | null
}

export interface PgConfigSnapshot {
  server_name: string
  pg_major_version: number | null
  is_superuser: boolean
  paths: { config_file: string | null; hba_file: string | null }
  settings: PgSetting[]
  file_settings: PgFileSetting[] | null
  file_settings_error: string | null
  hba_rules: PgHbaRule[] | null
  hba_error: string | null
}

export interface NotificationChannel {
  id: number
  name: string
  channel_type: string
  config_json: string
  is_active: boolean
}

export interface StructureSyncRun {
  id: number
  scenario_id: number
  task_id: string | null
  status: string
  current_step: string | null
  temp_db: string | null
  renamed_prod_to: string | null
  dropped_old: string[]
  generated_sql: string | null
  summary: {
    new_tables: number
    column_alters: number
    types: number
    matviews: number
    functions: number
    views: number
    triggers: number
    notes: string[]
    apply_errors?: string[]
    verify?: any
  } | null
  dry_run: boolean
  error_message: string | null
  started_at: string
  finished_at: string | null
}

export interface StructureSyncScenario {
  id: number
  name: string
  prod_server_id: number
  prod_server_name: string | null
  prod_database: string
  test_server_id: number
  test_server_name: string | null
  test_database: string
  target_server_id: number | null
  target_server_name: string | null
  target_name: string
  temp_name_template: string
  old_db_prefix: string
  keep_old_count: number
  data_copy_mode: string
  excluded_tables: string[]
  require_approval: boolean
  cron_expression: string | null
  is_active: boolean
  created_at: string
  last_run: StructureSyncRun | null
}

export interface AlertRule {
  id: number
  name: string
  rule_type: string
  threshold_json: string
  channel_id: number
  server_id: number | null
  is_active: boolean
}
