import axios from 'axios'
import type {
  ArtifactListResponse,
  CleanupResponse,
  Run,
  RunCreateRequest,
  RunListResponse,
  RunMetricsResponse,
  SettingsResponse,
  SettingsUpdateRequest,
  Verdict,
} from './types/api'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8080',
})

export async function listRuns(params?: Record<string, any>): Promise<RunListResponse> {
  const { data } = await api.get('/runs', { params })
  return data
}

export async function listRunMetrics(limit = 20): Promise<RunMetricsResponse> {
  const { data } = await api.get('/runs/metrics', { params: { limit } })
  return data
}

export async function createRun(payload: RunCreateRequest): Promise<Run> {
  const { data } = await api.post('/runs', payload)
  return data
}

export async function getRun(id: string): Promise<Run> {
  const { data } = await api.get(`/runs/${id}`)
  return data
}

export async function getVerdict(id: string): Promise<Verdict> {
  const { data } = await api.get(`/runs/${id}/verdict`)
  return data
}

export async function getArtifacts(id: string): Promise<ArtifactListResponse> {
  const { data } = await api.get(`/runs/${id}/artifacts`)
  return data
}

export async function cleanupRun(id: string): Promise<CleanupResponse> {
  const { data } = await api.post(`/runs/${id}/cleanup`)
  return data
}

export async function getSettings(): Promise<SettingsResponse> {
  const { data } = await api.get('/settings')
  return data
}

export async function updateSettings(payload: SettingsUpdateRequest): Promise<SettingsResponse> {
  const { data } = await api.put('/settings', payload)
  return data
}
