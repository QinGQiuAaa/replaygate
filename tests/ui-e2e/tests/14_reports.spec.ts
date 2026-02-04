import { test, expect } from '@playwright/test'
import { createRun, waitForRunCompleted } from './helpers'

test('reports tabs render data', async ({ page, request }) => {
  const run = await createRun(request, {
    name: `e2e-reports-${Date.now()}`,
    strict_tolerance: 0.15,
    runners: ['replay', 'perf'],
  })
  await waitForRunCompleted(request, run.id, 180_000)

  await page.goto(`/runs/${run.id}/reports`)
  const diffTab = page.getByRole('tab', { name: 'Diff' })
  const perfTab = page.getByRole('tab', { name: 'Perf' })
  await expect(diffTab).toBeVisible()
  await expect(perfTab).toBeVisible()

  await diffTab.click()
  await expect(page.getByTestId('reports-tab-diff')).toBeVisible()
  await expect(page.getByTestId('reports-json-view')).toBeVisible()

  await perfTab.click()
  await expect(page.getByTestId('reports-tab-perf')).toBeVisible()
  await expect(page.getByTestId('reports-json-view')).toBeVisible()

  await page.getByRole('tab', { name: 'Security' }).click()
  await page.getByRole('tab', { name: 'Compat' }).click()
  await page.getByRole('tab', { name: 'Obs' }).click()
})
