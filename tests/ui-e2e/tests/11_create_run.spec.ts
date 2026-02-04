import { test, expect } from '@playwright/test'
import { waitForRunCompleted } from './helpers'

test('create run from UI', async ({ page, request }) => {
  await page.goto('/runs/new')

  const replay = page.getByTestId('create-run-runner-replay')
  const perf = page.getByTestId('create-run-runner-perf')
  const replayInput = replay.locator('input')
  const perfInput = perf.locator('input')

  if (!(await replayInput.isChecked())) {
    await replay.click()
  }
  if (!(await perfInput.isChecked())) {
    await perf.click()
  }

  const strictInput = page.getByTestId('create-run-strict-tolerance').locator('input')
  await strictInput.fill('0.15')

  await page.getByTestId('create-run-submit').click()
  await page.waitForURL(/\/runs\/[^/]+\/overview/)

  const url = page.url()
  const match = /\/runs\/([^/]+)\/overview/.exec(url)
  expect(match).not.toBeNull()

  await expect(page.getByTestId('overview-overall-verdict')).toBeVisible()

  const runId = match?.[1]
  if (runId) {
    await waitForRunCompleted(request, runId)
  }
})
