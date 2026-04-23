import { test, expect } from '../fixtures'

test('broker can run plan comparison for a seeded client and see ranked plans', async ({ authedPage }) => {
  await authedPage.goto('/compare')
  // PlanComparisonPage has a client-selector <select>; first seeded client is Eleanor Rigby
  // (placeholder "— none —" at index 0, so Eleanor is at index 1).
  await authedPage.getByRole('combobox').first().selectOption({ index: 1 })
  await authedPage.getByRole('button', { name: /compare plans/i }).click()

  // Plan fetch hits real CMS data via the seeded backend — give it generous time
  const planRows = authedPage.getByTestId('plan-row')
  await expect(planRows.first()).toBeVisible({ timeout: 30_000 })
  await expect(planRows.first()).toContainText(/\$/)
})
