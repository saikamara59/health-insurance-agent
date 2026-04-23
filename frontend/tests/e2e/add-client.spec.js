import { test, expect } from '../fixtures'

test('broker can add a new client and see them in the list', async ({ authedPage }) => {
  await authedPage.goto('/clients/new')

  const name = `E2E Client ${Date.now()}`
  await authedPage.getByPlaceholder(/marjorie calloway/i).fill(name)
  await authedPage.getByPlaceholder('10025').fill('10001')
  // Use exact match: '67' is a substring of the insurance-ID placeholder '1356789012'.
  await authedPage.getByPlaceholder('67', { exact: true }).fill('67')
  await authedPage.getByRole('combobox').first().selectOption('low')
  await authedPage.getByRole('button', { name: /create client/i }).click()

  await authedPage.goto('/clients')
  await expect(authedPage.getByText(name)).toBeVisible()
})
