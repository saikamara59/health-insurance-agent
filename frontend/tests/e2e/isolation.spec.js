import { test, expect } from '../fixtures'

// Canary tests: if these ever run on different workers without isolation,
// the second test sees the first's client and fails.
//
// On the same worker, the per-test reset gives test B a clean slate, so
// they trivially pass. The meaningful case is parallel execution across
// workers — broker scoping is what guarantees B doesn't see A.

async function addClient(page, name) {
  await page.goto('/clients/new')
  await page.getByPlaceholder(/marjorie calloway/i).fill(name)
  await page.getByPlaceholder('10025').fill('10001')
  // Use exact match: '67' is a substring of the insurance-ID placeholder '1356789012'.
  await page.getByPlaceholder('67', { exact: true }).fill('67')
  await page.getByRole('combobox').first().selectOption('low')
  await page.getByRole('button', { name: /create client/i }).click()
}

test('isolation canary A: adds Probe-A and never sees Probe-B', async ({ authedPage }) => {
  await addClient(authedPage, 'Isolation-Probe-A')
  await authedPage.goto('/clients')
  await expect(authedPage.getByText('Isolation-Probe-A')).toBeVisible()
  await expect(authedPage.getByText('Isolation-Probe-B')).toHaveCount(0)
})

test('isolation canary B: adds Probe-B and never sees Probe-A', async ({ authedPage }) => {
  await addClient(authedPage, 'Isolation-Probe-B')
  await authedPage.goto('/clients')
  await expect(authedPage.getByText('Isolation-Probe-B')).toBeVisible()
  await expect(authedPage.getByText('Isolation-Probe-A')).toHaveCount(0)
})
