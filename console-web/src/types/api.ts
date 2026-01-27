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
  max_diff_rate?: number
  max_schema_breaking?: number
  max_strict_mismatches?: number
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
}

export interface Verdict {
  verdict?: VerdictStatus
  reasons?: VerdictReason[]
}

export interface RunCreateRequest {
  name: string
  recording_id: string
  baseline_base_url: string
  candidate_base_url: string
  baseline_version?: string
  candidate_version?: string
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
