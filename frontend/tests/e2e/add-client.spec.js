import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can add a new client and see them in the list', async ({ page, login }) => {
  await login(broker)
  await page.goto('/clients/new')

  const name = `E2E Client ${Date.now()}`
  // AddClientPage labels are visual-only (no htmlFor), so use placeholders
  await page.getByPlaceholder(/marjorie calloway/i).fill(name)
  await page.getByPlaceholder('10025').fill('10001')
  await page.getByPlaceholder('67').fill('67')
  await page.getByRole('combobox').first().selectOption('low')
  await page.getByRole('button', { name: /create client/i }).click()

  await page.goto('/clients')
  await expect(page.getByText(name)).toBeVisible()
})
