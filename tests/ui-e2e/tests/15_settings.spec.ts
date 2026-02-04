import { test, expect } from '@playwright/test'

test('settings persist after save', async ({ page }) => {
  await page.goto('/settings')

  await page.getByTestId('settings-default-executor').click()
  await page.getByRole('option', { name: 'local' }).click()

  const templateInput = page.getByTestId('settings-template-json')
  const raw = await templateInput.inputValue()
  let templates: any[] = []
  try {
    templates = JSON.parse(raw)
  } catch (error) {
    templates = []
  }
  const baseThresholds = templates[0]?.thresholds || {}
  const updatedTemplates = [
    ...templates.filter((item) => item.name !== 'e2e'),
    { name: 'e2e', thresholds: baseThresholds },
  ]
  await templateInput.fill(JSON.stringify(updatedTemplates, null, 2))

  const activeInput = page.locator('input[placeholder="default"]').first()
  await activeInput.fill('e2e')

  await page.getByTestId('settings-save').click()
  await page.waitForTimeout(1000)
  await page.reload()

  const reloadedJson = await page.getByTestId('settings-template-json').inputValue()
  expect(reloadedJson).toContain('"e2e"')
  await expect(page.locator('input[placeholder="default"]').first()).toHaveValue('e2e')
})
