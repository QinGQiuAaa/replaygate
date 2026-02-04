import { test, expect } from '@playwright/test'
import { createRun, waitForRunCompleted, getArtifacts } from './helpers'

test('run overview shows verdict and artifacts', async ({ page, request }) => {
  const run = await createRun(request, {
    name: `e2e-overview-${Date.now()}`,
    strict_tolerance: 0.15,
    runners: ['replay'],
  })
  await waitForRunCompleted(request, run.id)
  const artifacts = await getArtifacts(request, run.id)
  expect(artifacts.items?.length || 0).toBeGreaterThan(0)

  await page.goto(`/runs/${run.id}/overview`)
  await expect(page.getByTestId('overview-overall-verdict')).toBeVisible()
  await expect(page.getByTestId('overview-runner-card-replay')).toBeVisible()
  await expect(page.getByTestId('overview-download-diff')).toBeVisible()
})
