import { test, expect } from '@playwright/test'

test('home loads and navigation exists', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('ReplayGate Console')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByRole('button', { name: '任务列表' })).toBeVisible()
  await expect(page.getByRole('button', { name: '创建任务' })).toBeVisible()
  await expect(page.getByRole('button', { name: '设置' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByRole('main').getByText('Dashboard')).toBeVisible()
})
