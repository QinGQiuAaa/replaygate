import type { APIRequestContext } from '@playwright/test'
import { expect } from '@playwright/test'

export const apiBase = process.env.RG_API_BASE || 'http://localhost:8080'

const defaultRunPayload = {
  name: 'e2e-run',
  recording_id: 'demo',
  baseline_base_url: 'http://flashsale-gateway:8000',
  candidate_base_url: 'http://flashsale-gateway:8000',
  baseline_version: 'v1',
  candidate_version: 'v2',
  runners: ['replay'],
  executor: 'local',
  strict_tolerance: 0.05,
}

export async function createRun(request: APIRequestContext, overrides: Record<string, any> = {}) {
  const resp = await request.post(`${apiBase}/runs`, {
    data: {
      ...defaultRunPayload,
      ...overrides,
      name: overrides.name || `e2e-run-${Date.now()}`,
    },
  })
  expect(resp.ok()).toBeTruthy()
  return await resp.json()
}

export async function waitForRunCompleted(
  request: APIRequestContext,
  runId: string,
  timeoutMs = 180_000,
) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const resp = await request.get(`${apiBase}/runs/${runId}`)
    if (resp.ok()) {
      const data = await resp.json()
      if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        return data
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 2000))
  }
  throw new Error(`Run ${runId} did not complete within ${timeoutMs}ms`)
}

export async function getArtifacts(request: APIRequestContext, runId: string) {
  const resp = await request.get(`${apiBase}/runs/${runId}/artifacts`)
  expect(resp.ok()).toBeTruthy()
  return await resp.json()
}
