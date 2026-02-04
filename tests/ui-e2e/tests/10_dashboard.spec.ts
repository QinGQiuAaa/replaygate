import { test, expect } from '@playwright/test'

test('dashboard renders charts and summary', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('dash-passfail')).toBeVisible()
  await expect(page.getByTestId('dash-chart-p99')).toBeVisible()
  await expect(page.getByTestId('dash-chart-rps')).toBeVisible()
})
