import { test as base, expect } from '@playwright/test'
import { broker } from './test-users'

export { expect }

function apiOrigin(baseURL) {
  return baseURL.replace(':5173', ':8000')
}

export const test = base.extend({
  // Auto-reset DB before each test by calling the backend reset endpoint directly.
  page: async ({ page, baseURL }, use) => {
    const res = await fetch(`${apiOrigin(baseURL)}/__test/reset`, { method: 'POST' })
    if (!res.ok) {
      throw new Error(`DB reset failed: ${res.status} ${await res.text()}`)
    }
    await use(page)
  },

  // Pre-authenticated page. Resets the DB, logs in via the auth API (no UI form),
  // seeds the tokens into sessionStorage before any page script runs, then yields
  // a page that arrives at the app already authenticated.
  authedPage: async ({ context, baseURL, request }, use) => {
    const api = apiOrigin(baseURL)

    const resetRes = await request.post(`${api}/__test/reset`)
    if (!resetRes.ok()) {
      throw new Error(`DB reset failed: ${resetRes.status()} ${await resetRes.text()}`)
    }

    const loginRes = await request.post(`${api}/auth/login`, {
      data: { email: broker.email, password: broker.password },
    })
    if (!loginRes.ok()) {
      throw new Error(`API login failed: ${loginRes.status()} ${await loginRes.text()}`)
    }
    const { access_token, refresh_token } = await loginRes.json()

    await context.addInitScript(([access, refresh]) => {
      sessionStorage.setItem('hf_token', access)
      sessionStorage.setItem('hf_refresh', refresh)
    }, [access_token, refresh_token])

    const page = await context.newPage()
    await use(page)
  },

  // UI-based login helper. Retained for tests that specifically exercise the login form.
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
