import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can log in and reach the dashboard', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(broker.email)
  await page.getByLabel(/credentials/i).fill(broker.password)
  await page.getByRole('button', { name: /authenticate/i }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: /good morning/i })).toBeVisible()
})

test('invalid credentials show an error', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(broker.email)
  await page.getByLabel(/credentials/i).fill('wrong-password')
  await page.getByRole('button', { name: /authenticate/i }).click()
  await expect(page.getByText(/authentication failed|invalid|incorrect/i)).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test('logged-in broker can sign out', async ({ page, login }) => {
  await login(broker)
  await page.getByRole('button', { name: /sign out/i }).click()
  await expect(page).toHaveURL(/\/login/)
})
