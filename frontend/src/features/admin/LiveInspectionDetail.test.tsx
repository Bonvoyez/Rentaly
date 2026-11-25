import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { adminApi, type InspectionDetail } from '../../services/admin-api'
import { LiveInspectionDetail } from './LiveInspectionDetail'

vi.mock('../../services/admin-api', () => ({
  adminApi: { detail: vi.fn(), image: vi.fn(), confirm: vi.fn(), retroactiveReject: vi.fn() },
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

it('selects rejection for a pending inspection whose AI verdict is FAIL', async () => {
  const pendingDetail = {
    inspection_id: 'inspection-pending', equipment_id: 'RPI4-001', primary_verdict: 'FAIL',
    final_status: 'PENDING_REVIEW', inspected_at: '2026-11-25T13:49:28+09:00', images: [], audit_logs: [],
  } as InspectionDetail
  vi.mocked(adminApi.detail).mockResolvedValue(pendingDetail)

  render(<MemoryRouter initialEntries={['/admin/inspections/inspection-pending']}><Routes><Route path="/admin/inspections/:inspectionId" element={<LiveInspectionDetail />} /></Routes></MemoryRouter>)

  expect(await screen.findByRole('button', { name: '반려' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: '승인' })).toHaveAttribute('aria-pressed', 'false')
})

it('allows an admin to change PASS to a rejection using the retroactive API', async () => {
  const passDetail = {
    inspection_id: 'inspection-1', equipment_id: 'device-1', primary_verdict: 'PASS',
    final_status: 'PASS', inspected_at: '2026-11-22T15:49:52+09:00', images: [], audit_logs: [],
  } as InspectionDetail
  vi.mocked(adminApi.detail).mockResolvedValue(passDetail)
  vi.mocked(adminApi.retroactiveReject).mockResolvedValue({ ...passDetail, final_status: 'CONFIRMED_REJECT' })

  render(<MemoryRouter initialEntries={['/admin/inspections/inspection-1']}><Routes><Route path="/admin/inspections/:inspectionId" element={<LiveInspectionDetail />} /></Routes></MemoryRouter>)

  const reject = await screen.findByRole('button', { name: '반려' })
  expect(reject).toBeEnabled()
  expect(screen.getByRole('button', { name: '판정 수정' })).toBeEnabled()
  fireEvent.click(reject)
  fireEvent.click(screen.getByRole('button', { name: '판정 수정' }))
  expect(screen.getByRole('alert')).toBeVisible()
  expect(adminApi.retroactiveReject).not.toHaveBeenCalled()
  const memo = screen.getByPlaceholderText('수정하려면 사유를 입력해주세요')
  expect(memo).toBeRequired()
  fireEvent.change(memo, { target: { value: '외관 결함 확인' } })
  fireEvent.click(screen.getByRole('button', { name: '판정 수정' }))
  fireEvent.click(screen.getByRole('button', { name: '확정' }))

  await waitFor(() => expect(adminApi.retroactiveReject).toHaveBeenCalledWith('inspection-1', '외관 결함 확인'))
  expect(adminApi.confirm).not.toHaveBeenCalled()
})

it('requires a memo when changing a saved rejection to approval', async () => {
  const rejectedDetail = {
    inspection_id: 'inspection-2', equipment_id: 'device-2', primary_verdict: 'FAIL',
    final_status: 'CONFIRMED_REJECT', inspected_at: '2026-11-22T15:49:52+09:00', images: [], audit_logs: [],
  } as InspectionDetail
  vi.mocked(adminApi.detail).mockResolvedValue(rejectedDetail)
  vi.mocked(adminApi.confirm).mockResolvedValue({ ...rejectedDetail, final_status: 'CONFIRMED_PASS' })

  render(<MemoryRouter initialEntries={['/admin/inspections/inspection-2']}><Routes><Route path="/admin/inspections/:inspectionId" element={<LiveInspectionDetail />} /></Routes></MemoryRouter>)

  fireEvent.click(await screen.findByRole('button', { name: '승인' }))
  const memo = screen.getByPlaceholderText('수정하려면 사유를 입력해주세요')
  expect(memo).toBeRequired()
  fireEvent.change(memo, { target: { value: '재검토 결과 정상' } })
  fireEvent.click(screen.getByRole('button', { name: '판정 수정' }))
  fireEvent.click(screen.getByRole('button', { name: '확정' }))

  await waitFor(() => expect(adminApi.confirm).toHaveBeenCalledWith('inspection-2', 'CONFIRMED_PASS', '재검토 결과 정상'))
})
