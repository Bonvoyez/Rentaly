import { afterEach, expect, it, vi } from 'vitest'
import { adminApi } from './admin-api'

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear() })

it('sends the backend account field and retains the issued token when login succeeds', async () => {
  let body: unknown
  const fetch = vi.fn(async (request: Request) => {
    body = await request.clone().json()
    return new Response(JSON.stringify({ access_token: 'test-token', expires_in: 7200 }))
  })
  vi.stubGlobal('fetch', fetch)
  await adminApi.login('operator', 'test-password')
  expect(body).toEqual({ account: 'operator', password: 'test-password' })
  expect(sessionStorage.getItem('rentaly-token')).toBe('test-token')
})

it('clears credentials when a protected request returns unauthorized', async () => {
  sessionStorage.setItem('rentaly-token', 'expired-token')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 401 })))
  await expect(adminApi.me()).rejects.toThrow()
  expect(sessionStorage.getItem('rentaly-token')).toBeNull()
})
