import { test as base, expect } from '@playwright/test'

export { expect }

export const test = base.extend({
  // Auto-reset DB before each test by calling the backend reset endpoint directly.
  page: async ({ page, baseURL }, use) => {
    const apiURL = baseURL.replace(':5173', ':8000')
    const res = await fetch(`${apiURL}/__test/reset`, { method: 'POST' })
    if (!res.ok) {
      throw new Error(`DB reset failed: ${res.status} ${await res.text()}`)
    }
    await use(page)
  },
  // Reusable login helper. Usage: await login(broker)
  login: async ({ page }, use) => {
    await use(async (creds) => {
      await page.goto('/login')
      await page.getByLabel(/work email/i).fill(creds.email)
      await page.getByLabel(/credentials/i).fill(creds.password)
      await page.getByRole('button', { name: /authenticate/i }).click()
      await page.waitForURL('/')
    })
  },
})
