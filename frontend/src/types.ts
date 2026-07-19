export type StatusLabel = 'Safe' | 'Warning' | 'Blocking'

export interface Metrics {
  schemaChangesDetected?: number
  blockingConflicts?: number
  affectedRows?: number
  approvedActions?: number
  dryRunStatus?: string
  transferredRows?: number
  validationFailures?: number
  breakingChanges?: number
  tablesAdded?: number
  tablesRemoved?: number
  columnsChanged?: number
  constraintsChanged?: number
}

export interface Conflict {
  id: number
  conflict_id: string
  schema_name: string
  table_name: string
  column_name: string
  constraint_name: string
  category: string
  object_type: 'table' | 'column' | 'constraint' | 'index' | 'enum' | 'sequence'
  change_type: 'added' | 'removed' | 'changed' | 'renamed'
  severity: StatusLabel
  breaking: boolean
  production_definition: Record<string, unknown>
  development_definition: Record<string, unknown>
  affected_row_count: number
  sample_values: unknown[]
  evidence: Record<string, unknown>
  preflight_status: 'not_run' | 'checked' | 'unsupported_preflight' | 'error'
  preflight_explanation: string
  sql_preview: string
  strategies: string[]
}

export interface RemediationPlan {
  id: number
  provider: string
  model: string
  risk_level: StatusLabel
  explanation: string
  content: {
    overall_risk_level: StatusLabel
    short_explanation: string
    blocking_issues: string[]
    ordered_recommended_actions: unknown[]
    alternative_strategies: string[]
    actions_requiring_human_approval: string[]
    validation_checks: string[]
    rollback_considerations: string[]
  }
  created_at: string
}

export interface ApprovedAction {
  id: number
  conflict_id: string
  action_type: string
  parameters: Record<string, unknown>
  rationale: string
  requires_approval: boolean
  approved: boolean
  status: string
  sql_preview: string
}

export interface DryRunLog {
  id: number
  sequence: number
  step: string
  status: string
  message: string
  rows_affected: number
  sql_preview: string
}

export interface AnalysisRun {
  id: number
  status: string
  title: string
  mode: 'demo' | 'live'
  locale: 'kk' | 'ru' | 'en'
  production_profile: number | null
  development_profile: number | null
  source_metadata: {
    production?: Record<string, unknown>
    development?: Record<string, unknown>
  }
  selected_schemas: string[]
  ignored_tables: string[]
  run_preflight: boolean
  ai_provider: string
  ai_model: string
  metrics: Metrics
  report: Record<string, unknown>
  error: string
  dry_run_status: string
  created_at: string
  updated_at: string
  conflicts: Conflict[]
  remediation_plan?: RemediationPlan
  actions: ApprovedAction[]
  dry_run_logs: DryRunLog[]
}

export interface ConnectionInfo {
  id: number | string
  target?: string
  name: string
  role: 'production' | 'development' | 'staging'
  host: string
  port: number
  database: string
  username: string
  passwordSet: boolean
  readOnly: boolean
  sslmode: 'disable' | 'allow' | 'prefer' | 'require' | 'verify-ca' | 'verify-full'
  selected_schemas: string[]
  statement_timeout: number
  last_test_status: string
  last_test_message: string
  last_tested_at: string | null
  is_demo: boolean
}

export interface ConnectionPayload {
  name: string
  role: 'production' | 'development' | 'staging'
  host: string
  port: number
  database: string
  username: string
  password?: string
  sslmode: ConnectionInfo['sslmode']
  selected_schemas: string[]
  statement_timeout: number
}

export interface AnalysisRequest {
  mode: 'demo' | 'live'
  locale?: 'kk' | 'ru' | 'en'
  production_profile_id?: number
  development_profile_id?: number
  schemas?: string[]
  ignored_tables?: string[]
  run_preflight?: boolean
}
