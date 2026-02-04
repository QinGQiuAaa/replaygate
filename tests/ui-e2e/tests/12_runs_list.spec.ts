import { test, expect } from '@playwright/test'
import { createRun, waitForRunCompleted } from './helpers'

test('runs list filters and pagination', async ({ page, request }) => {
  const run = await createRun(request, {
    name: `e2e-list-${Date.now()}`,
    strict_tolerance: 0.15,
    runners: ['replay'],
  })
  await waitForRunCompleted(request, run.id)

  await page.goto('/runs')
  await expect(page.getByTestId('runs-pagination')).toBeVisible()

  await page.getByTestId('runs-filter-verdict').click()
  await page.getByRole('option', { name: 'PASS' }).click()

  await page.getByTestId('runs-filter-runner').click()
  await page.getByRole('option', { name: 'replay' }).click()

  await page.getByPlaceholder('开始').fill('2020-01-01T00:00:00')
  await page.getByPlaceholder('结束').fill('2030-01-01T00:00:00')

  await page.getByRole('button', { name: '应用' }).click()
  await expect(page.getByText(run.name)).toBeVisible()
})
