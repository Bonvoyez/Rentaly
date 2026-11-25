import ky from 'ky'
import { z } from 'zod'

function normalizeInspectionTime(value: string): string {
  const match = /^(\d{4})-(\d{1,2})-(\d{1,2}) (오전|오후) (\d{1,2}):(\d{2}):(\d{2})$/.exec(value)
  if (!match) return value
  const [, year, month, day, period, hour, minute, second] = match
  const hours = Number(hour) % 12 + (period === '오후' ? 12 : 0)
  return new Date(Number(year), Number(month) - 1, Number(day), hours, Number(minute), Number(second)).toISOString()
}

export const summarySchema = z.object({
  inspection_id: z.string(), equipment_id: z.string(), recognized_serial_number: z.string().nullable().optional(),
  primary_verdict: z.string(), final_status: z.string().transform(value => value === 'PASSED' ? 'PASS' : value === 'FAILED' ? 'FAIL' : value), inspected_at: z.string().transform(normalizeInspectionTime),
  total_duration_ms: z.number().nullable().optional(),
})
const detailSchema = summarySchema.extend({
  ai_result: z.object({ pwr_led_status: z.boolean(), detected_defects: z.unknown().optional(), model_version: z.string() }).nullable().optional(),
  images: z.array(z.object({ image_id: z.string() })).default([]),
  audit_logs: z.array(z.object({ audit_id: z.string(), action: z.string(), reason: z.string().nullable().optional(), created_at: z.string() })).default([]),
})
export type InspectionSummary = z.infer<typeof summarySchema>
export type InspectionDetail = z.infer<typeof detailSchema>
const client = ky.create({ timeout: 15000, retry: 0 })
const baseUrl = () => (import.meta.env.VITE_API_BASE_URL || 'https://rentaly.duckdns.org').replace(/\/$/, '')
export const clearSession = () => { sessionStorage.removeItem('rentaly-token') }
async function request(path: string, options: { readonly method?: 'POST'; readonly json?: unknown } = {}) {
  const token = sessionStorage.getItem('rentaly-token')
  const response = await client(`${baseUrl()}/api/v1/admin/${path}`, {
    ...options, headers: token ? { Authorization: `Bearer ${token}` } : {},
    hooks: { afterResponse: [({ response: result }) => {
      if (result.status === 401) {
        clearSession()
        if (path !== 'auth/login') window.dispatchEvent(new Event('rentaly-session-expired'))
      }
    }] },
  })
  return response
}
export const adminApi = {
  async login(account: string, password: string) {
    clearSession()
    const data = z.object({ access_token: z.string().min(1) }).parse(await (await request('auth/login', { method: 'POST', json: { account, password } })).json())
    sessionStorage.setItem('rentaly-token', data.access_token)
  },
  async me() { return z.object({ account: z.string(), role: z.string() }).parse(await (await request('auth/me')).json()) },
  async list(skip: number) { return z.array(summarySchema).parse(await (await request(`inspections?skip=${skip}&limit=100`)).json()) },
  async pending(skip: number) { return z.array(summarySchema).parse(await (await request(`inspections/pending?skip=${skip}&limit=100`)).json()) },
  async detail(id: string) { return detailSchema.parse(await (await request(`inspections/${encodeURIComponent(id)}`)).json()) },
  async image(id: string) { return (await request(`images/${encodeURIComponent(id)}`)).blob() },
  async confirm(id: string, decision: 'CONFIRMED_PASS' | 'CONFIRMED_REJECT', reason: string) {
    return detailSchema.parse(await (await request(`inspections/${encodeURIComponent(id)}/confirm`, { method: 'POST', json: { decision, reason: reason || null } })).json())
  },
  async retroactiveReject(id: string, reason: string) {
    return detailSchema.parse(await (await request(`inspections/${encodeURIComponent(id)}/retroactive-reject`, { method: 'POST', json: { reason } })).json())
  },
}
