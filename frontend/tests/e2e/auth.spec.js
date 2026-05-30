import { test, expect } from '../fixtures'

test('broker can log in and reach the dashboard', async ({ page, workerBroker }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(workerBroker.email)
  await page.getByLabel(/credentials/i).fill(workerBroker.password)
  // Submit button labeled "Sign in" in login mode (was "Authenticate" before
  // the brand-button rename); /dashboard is the workspace home now that /
  // serves the public landing page when logged out.
  await page.getByRole('button', { name: /^sign in$/i }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: /good morning/i })).toBeVisible()
})

test('invalid credentials show an error', async ({ page, workerBroker }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(workerBroker.email)
  await page.getByLabel(/credentials/i).fill('wrong-password')
  await page.getByRole('button', { name: /^sign in$/i }).click()
  // Backend returns "Invalid email or password" for a bad password; the
  // login form surfaces whichever message the api client passes through.
  await expect(page.getByText(/invalid|incorrect|session/i)).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test('logged-in broker can sign out', async ({ authedPage }) => {
  await authedPage.goto('/dashboard')
  await authedPage.getByRole('button', { name: /sign out/i }).click()
  await expect(authedPage).toHaveURL(/\/login/)
})
