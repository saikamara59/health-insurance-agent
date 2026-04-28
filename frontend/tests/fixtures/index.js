import { test as base, expect } from '@playwright/test'
import { workerBroker } from './test-users'

export { expect }

function apiOrigin(baseURL) {
  return baseURL.replace(':5173', ':8000')
}

async function resetForWorker(api, workerId, requester = fetch) {
  const res = await requester(`${api}/__test/reset`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ worker_id: workerId }),
  })
  const ok = typeof res.ok === 'function' ? res.ok() : res.ok
  if (!ok) {
    const text = await res.text()
    const status = typeof res.status === 'function' ? res.status() : res.status
    throw new Error(`DB reset failed: ${status} ${text}`)
  }
}

export const test = base.extend({
  // Per-worker broker identity (sticky across all tests on this worker).
  workerBroker: [async ({}, use, workerInfo) => {
    await use(workerBroker(workerInfo.parallelIndex))
  }, { scope: 'worker' }],

  // Auto-reset this worker's broker-scoped data before each test.
  page: async ({ page, baseURL, workerBroker }, use) => {
    await resetForWorker(apiOrigin(baseURL), workerBroker.workerId)
    await use(page)
  },

  // Pre-authenticated page using the worker's broker identity.
  authedPage: async ({ context, baseURL, request, workerBroker }, use) => {
    const api = apiOrigin(baseURL)
    await resetForWorker(api, workerBroker.workerId, (url, init) => request.fetch(url, init))

    const loginRes = await request.post(`${api}/auth/login`, {
      data: { email: workerBroker.email, password: workerBroker.password },
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

  // UI-based login helper, retained for tests that exercise the login form.
  login: async ({ page, workerBroker }, use) => {
    await use(async (creds) => {
      const credsToUse = creds ?? workerBroker
      await page.goto('/login')
      await page.getByLabel(/work email/i).fill(credsToUse.email)
      await page.getByLabel(/credentials/i).fill(credsToUse.password)
      await page.getByRole('button', { name: /authenticate/i }).click()
      await page.waitForURL('/')
    })
  },
})
