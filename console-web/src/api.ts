import axios from 'axios'
import type { ArtifactListResponse, CleanupResponse, Run, RunCreateRequest, RunListResponse, Verdict } from './types/api'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8080',
})

export async function listRuns(): Promise<RunListResponse> {
  const { data } = await api.get('/runs')
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
