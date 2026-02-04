export type RunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
export type VerdictStatus = 'PASS' | 'FAIL'

export interface DiffRules {
  global_ignore?: string[]
  endpoint_rules?: Record<string, EndpointRule>
  numeric_tolerance?: number
}

export interface EndpointRule {
  ignore?: string[]
  strict?: string[]
  numeric_tolerance?: number
}

export interface GateThresholds {
  replay?: ReplayThresholds
  perf?: PerfThresholds
  security?: SecurityThresholds
  compat?: CompatThresholds
  obs?: ObsThresholds
  max_diff_rate?: number
  max_schema_breaking?: number
  max_strict_mismatches?: number
}

export interface ReplayThresholds {
  max_diff_rate?: number
  max_schema_breaking?: number
  max_strict_mismatches?: number
}

export interface PerfThresholds {
  max_error_rate_pct?: number
  max_p99_ms?: number
  vus?: number
  duration?: string
}

export interface ObsThresholds {
  max_error_rate_pct?: number
  max_p99_ms?: number
  window?: string
}

export interface SecurityThresholds {
  max_high?: number
  max_medium?: number
}

export interface CompatThresholds {
  max_breaking_changes?: number
  mode?: string
}

export interface DiffSummary {
  diff_rate?: number
  total_fields?: number
  diff_fields?: number
  strict_mismatches?: number
  strict_max_drift?: number
  strict_tolerance_used?: number
  schema_breaking?: number
  numeric_drift?: number
  total_requests?: number
}

export interface VerdictReason {
  domain?: string
  rule_or_metric?: string
  observed?: string
  threshold?: string
  time_window?: string
  evidence_link?: string
  baseline_run_id?: string
}

export interface Verdict {
  verdict?: VerdictStatus
  reasons?: VerdictReason[]
}

export interface RunnerResult {
  name?: string
  verdict?: VerdictStatus
  reasons?: VerdictReason[]
  artifacts_files?: string[]
  metrics?: Record<string, any>
}

export interface OverallVerdict {
  overall_verdict?: VerdictStatus
  runner_results?: RunnerResult[]
}

export interface RunCreateRequest {
  name: string
  recording_id: string
  baseline_base_url: string
  candidate_base_url: string
  baseline_version?: string
  candidate_version?: string
  baseline_run_id?: string
  runners?: string[]
  executor?: string
  strict_tolerance?: number
  rules?: DiffRules
  thresholds?: GateThresholds
}

export interface Run {
  id?: string
  name?: string
  status?: RunStatus
  recording_id?: string
  baseline_base_url?: string
  candidate_base_url?: string
  baseline_version?: string
  candidate_version?: string
  baseline_run_id?: string
  executor?: string
  runners?: string[]
  runner_results?: RunnerResult[]
  overall_verdict?: VerdictStatus
  strict_tolerance?: number
  rules?: DiffRules
  thresholds?: GateThresholds
  created_at?: string
  started_at?: string | null
  finished_at?: string | null
  diff_summary?: DiffSummary
  verdict?: Verdict
  error_message?: string | null
}

export interface RunListResponse {
  items: Run[]
  page?: number
  page_size?: number
  total?: number
}

export interface RunMetric {
  id?: string
  created_at?: string
  overall_verdict?: VerdictStatus
  p99_ms?: number | null
  error_rate_pct?: number | null
  rps?: number | null
}

export interface RunMetricsResponse {
  items: RunMetric[]
  summary?: {
    pass?: number
    fail?: number
  }
}

export interface ThresholdTemplate {
  name: string
  thresholds: Record<string, any>
}

export interface SettingsUpdateRequest {
  default_executor?: string
  threshold_templates?: ThresholdTemplate[]
  active_template?: string
}

export interface SettingsResponse {
  default_executor: string
  threshold_templates: ThresholdTemplate[]
  active_template: string
  env: Record<string, any>
}

export interface ArtifactItem {
  name?: string
  size_bytes?: number
  download_url?: string
}

export interface ArtifactListResponse {
  items: ArtifactItem[]
}

export interface CleanupResponse {
  status?: string
  cleaned_at?: string
}
