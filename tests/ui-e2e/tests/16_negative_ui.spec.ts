import { test, expect } from '@playwright/test'

test('create run validation and executor warning', async ({ page }) => {
  await page.goto('/runs/new')

  const replay = page.getByTestId('create-run-runner-replay')
  const replayInput = replay.locator('input')
  if (await replayInput.isChecked()) {
    await replay.click()
  }

  await page.getByTestId('create-run-submit').click()
  await expect(page.getByText(/Select at least one runner/)).toBeVisible()

  await replay.click()
  const strictInput = page.getByTestId('create-run-strict-tolerance').locator('input')
  await strictInput.fill('2')
  await page.getByTestId('create-run-submit').click()
  await expect(page.getByText('Strict tolerance must be between 0 and 1')).toBeVisible()

  await page.getByTestId('create-run-executor').click()
  await page.getByRole('option', { name: 'k8s' }).click()
  await expect(page.getByText('K8s executor is not enabled')).toBeVisible()
})
