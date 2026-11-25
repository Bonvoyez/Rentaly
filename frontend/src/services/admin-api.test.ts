import { afterEach, expect, it, vi } from 'vitest'
import { adminApi, summarySchema } from './admin-api'

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear() })

it('maps the deployed inspection status and Korean timestamp to UI values', () => {
  const result = summarySchema.parse({ inspection_id: 'id', equipment_id: 'device', primary_verdict: 'PASS', final_status: 'PASSED', inspected_at: '2026-11-22 오후 3:49:52' })
  expect(result.final_status).toBe('PASS')
  expect(new Date(result.inspected_at).getHours()).toBe(15)
})

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

it('uses the dedicated pending inspection endpoint', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
  vi.stubGlobal('fetch', fetch)
  expect(await adminApi.pending(0)).toEqual([])
  expect(fetch.mock.calls[0][0].url).toContain('/api/v1/admin/inspections/pending?skip=0&limit=100')
})

it('sends the required reason to the retroactive rejection endpoint', async () => {
  let requestUrl = ''
  let requestBody: unknown
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    requestUrl = request.url
    requestBody = await request.clone().json()
    return new Response(JSON.stringify({
      inspection_id: 'inspection-1', equipment_id: 'device-1', primary_verdict: 'PASS',
      final_status: 'CONFIRMED_REJECT', inspected_at: '2026-11-22T15:49:52+09:00',
    }))
  }))

  await adminApi.retroactiveReject('inspection-1', '외관 결함 확인')

  expect(requestUrl).toContain('/api/v1/admin/inspections/inspection-1/retroactive-reject')
  expect(requestBody).toEqual({ reason: '외관 결함 확인' })
})
