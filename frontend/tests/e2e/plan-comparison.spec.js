import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can run plan comparison for a seeded client and see ranked plans', async ({ page, login }) => {
  await login(broker)
  await page.goto('/compare')
  // PlanComparisonPage has a client-selector <select>; seed_data.py provides Eleanor Rigby
  await page.getByRole('combobox').first().selectOption({ label: /eleanor rigby/i })
  await page.getByRole('button', { name: /compare plans/i }).click()

  // Plan fetch hits real CMS data via the seeded backend — give it generous time
  const planRows = page.getByTestId('plan-row')
  await expect(planRows.first()).toBeVisible({ timeout: 30_000 })
  await expect(planRows.first()).toContainText(/\$/)
})
