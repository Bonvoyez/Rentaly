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

  expect(await screen.findByRole('button', { name: 'Reject' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Approve' })).toHaveAttribute('aria-pressed', 'false')
})

it('allows an admin to change PASS to a rejection using the retroactive API', async () => {
  const passDetail = {
    inspection_id: 'inspection-1', equipment_id: 'device-1', primary_verdict: 'PASS',
    final_status: 'PASS', inspected_at: '2026-11-22T15:49:52+09:00', images: [], audit_logs: [],
  } as InspectionDetail
  vi.mocked(adminApi.detail).mockResolvedValue(passDetail)
  vi.mocked(adminApi.retroactiveReject).mockResolvedValue({ ...passDetail, final_status: 'CONFIRMED_REJECT' })

  render(<MemoryRouter initialEntries={['/admin/inspections/inspection-1']}><Routes><Route path="/admin/inspections/:inspectionId" element={<LiveInspectionDetail />} /></Routes></MemoryRouter>)

  const reject = await screen.findByRole('button', { name: 'Reject' })
  expect(reject).toBeEnabled()
  expect(screen.getByRole('button', { name: 'Update Verdict' })).toBeEnabled()
  fireEvent.click(reject)
  fireEvent.click(screen.getByRole('button', { name: 'Update Verdict' }))
  expect(screen.getByRole('alert')).toBeVisible()
  expect(adminApi.retroactiveReject).not.toHaveBeenCalled()
  const memo = screen.getByPlaceholderText('Enter a reason to update')
  expect(memo).toBeRequired()
  fireEvent.change(memo, { target: { value: 'Exterior defect confirmed' } })
  fireEvent.click(screen.getByRole('button', { name: 'Update Verdict' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

  await waitFor(() => expect(adminApi.retroactiveReject).toHaveBeenCalledWith('inspection-1', 'Exterior defect confirmed'))
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

  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  const memo = screen.getByPlaceholderText('Enter a reason to update')
  expect(memo).toBeRequired()
  fireEvent.change(memo, { target: { value: 'Normal upon re-review' } })
  fireEvent.click(screen.getByRole('button', { name: 'Update Verdict' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

  await waitFor(() => expect(adminApi.confirm).toHaveBeenCalledWith('inspection-2', 'CONFIRMED_PASS', 'Normal upon re-review'))
})
