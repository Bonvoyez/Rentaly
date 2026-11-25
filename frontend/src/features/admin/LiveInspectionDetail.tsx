import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, InspectionCheck, StatusBadge } from '../../components/ui'
import { adminApi, type InspectionDetail } from '../../services/admin-api'
import { VerdictOption } from './InspectionDetailPage'

type Verdict = 'CONFIRMED_PASS' | 'CONFIRMED_REJECT'

function initialVerdict(detail: InspectionDetail): Verdict {
  return detail.final_status.includes('REJECT') ||
    (detail.final_status === 'PENDING_REVIEW' && detail.primary_verdict === 'FAIL')
    ? 'CONFIRMED_REJECT' : 'CONFIRMED_PASS'
}

export function LiveInspectionDetail() {
  const navigate = useNavigate()
  const { inspectionId = '' } = useParams()
  const [detail, setDetail] = useState<InspectionDetail>()
  const [imageUrl, setImageUrl] = useState('')
  const [error, setError] = useState('')
  const [reason, setReason] = useState('')
  const [memoError, setMemoError] = useState(false)
  const [verdict, setVerdict] = useState<Verdict>('CONFIRMED_PASS')
  const [confirming, setConfirming] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    let objectUrl = ''
    void adminApi.detail(inspectionId).then(async result => {
      if (!active) return
      setDetail(result)
      setVerdict(initialVerdict(result))
      const image = result.images[0]
      if (image) {
        try {
          const blob = await adminApi.image(image.image_id)
          if (active) { objectUrl = URL.createObjectURL(blob); setImageUrl(objectUrl) }
        } catch { if (active) setError('Failed to load inspection image.') }
      }
    }).catch(() => { if (active) setError('Failed to load inspection details.') })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [inspectionId])

  const pending = detail?.final_status === 'PENDING_REVIEW'
  const passed = detail?.final_status === 'PASS' || detail?.final_status === 'CONFIRMED_PASS'
  const rejected = detail?.final_status.includes('REJECT') ?? false
  const editable = pending || passed || rejected
  const savedVerdict: Verdict = detail ? initialVerdict(detail) : 'CONFIRMED_PASS'
  const reasonRequired = editable && verdict !== savedVerdict
  const led = detail?.ai_result?.pwr_led_status
  const defects = detail?.ai_result?.detected_defects
  const defectsFound = Array.isArray(defects) && defects.length > 0

  function requestSave() {
    if (!pending && verdict === savedVerdict) {
      setError('Please select a verdict to update.')
      return
    }
    if (reasonRequired && !reason.trim()) {
      setMemoError(true)
      return
    }
    setError('')
    setMemoError(false)
    setConfirming(true)
  }

  async function save() {
    if (!detail) return
    setSaving(true)
    setError('')
    try {
      const updated = pending
        ? await adminApi.confirm(inspectionId, verdict, reason.trim())
        : passed
          ? await adminApi.retroactiveReject(inspectionId, reason.trim())
          : await adminApi.confirm(inspectionId, verdict, reason.trim())
      setDetail(updated)
      setVerdict(initialVerdict(updated))
      setReason('')
      setConfirming(false)
    } catch {
      setError('Failed to save verdict. Please check the inspection status and reason.')
      setConfirming(false)
    } finally { setSaving(false) }
  }

  return <section className="min-h-full px-4 pb-8 pt-6 sm:px-6 md:px-10 md:pb-10 md:pt-8">
    <h1 className="text-[28px] font-bold tracking-tight">Inspection Details</h1>
    <p className="mt-3 break-all text-[13px] text-secondary">Inspection ID · {inspectionId}</p>
    {error && <p role="alert" className="mt-5 text-danger dark:text-rose-300">{error}</p>}
    {!detail ? <p role="status" className="mt-8">{error || 'Loading inspection details…'}</p> : <>
      <div className="mt-6 grid gap-4 md:mt-8 md:gap-7 lg:grid-cols-2">
        <section className="min-w-0 rounded-2xl border border-line-soft bg-slate-50 p-3 sm:p-4 lg:h-[420px] dark:border-dark-line dark:bg-dark-raised">
          <div className="grid aspect-[4/3] max-h-[324px] place-items-center overflow-hidden rounded-xl bg-slate-200 text-muted dark:bg-dark-canvas">
            {imageUrl ? <img src={imageUrl} alt="Raspberry Pi board captured during inspection" className="h-full w-full object-contain" /> : 'No captured image'}
          </div>
          <p className="mt-4 text-xs text-secondary lg:mt-5 dark:text-dark-secondary">Captured board image</p>
        </section>
        <section className="min-w-0 rounded-2xl border border-line-soft p-4 sm:p-5 lg:h-[420px] dark:border-dark-line dark:bg-dark-raised">
          <h2 className="text-[17px] font-bold">Inspection Info</h2>
          <dl className="mt-5 grid grid-cols-[minmax(92px,38%)_1fr] gap-y-4 text-xs sm:gap-y-5">
            {[
              ['Device', detail.equipment_id],
              ['Inspected At', new Date(detail.inspected_at).toLocaleString('en-US')],
              ['Serial Number', detail.recognized_serial_number || '—'],
              ['Power LED', led === undefined ? 'Not Run' : led ? 'Normal' : 'Needs Review'],
              ['Exterior', !detail.ai_result ? 'Not Run' : defectsFound ? 'Needs Review' : 'Normal'],
              ['Duration', detail.total_duration_ms == null ? '—' : `${(detail.total_duration_ms / 1000).toFixed(1)}s`],
            ].map(([label, value]) => <div key={label} className="contents"><dt className="text-secondary dark:text-dark-secondary">{label}</dt><dd className="min-w-0 break-words font-semibold">{value}</dd></div>)}
            <dt className="text-secondary dark:text-dark-secondary">Status</dt>
            <dd><StatusBadge tone={pending || rejected ? 'warning' : detail.final_status === 'ERROR' ? 'error' : 'success'}>{detail.final_status}</StatusBadge></dd>
          </dl>
        </section>
        <section className="grid min-w-0 gap-2.5 rounded-2xl border border-line-soft p-4 lg:min-h-[210px] dark:border-dark-line dark:bg-dark-raised" aria-label="Inspection checks">
          <InspectionCheck label="PWR LED Status" state={led === undefined ? 'Not Run' : led ? 'Normal' : 'Needs Review'} tone={led === undefined ? 'muted' : led ? 'success' : 'warning'} />
          <InspectionCheck label="Exterior Inspection" state={!detail.ai_result ? 'Not Run' : defectsFound ? 'Needs Review' : 'Normal'} tone={!detail.ai_result ? 'muted' : defectsFound ? 'warning' : 'success'} />
          <InspectionCheck label="Serial Recognition" state={detail.recognized_serial_number ? 'Verified' : 'Unrecognized'} tone={detail.recognized_serial_number ? 'success' : 'muted'} />
        </section>
        <section className="min-w-0 rounded-2xl border border-line-soft p-4 lg:min-h-[210px] dark:border-dark-line dark:bg-dark-raised">
          <h2 className="text-[17px] font-bold">Admin Final Verdict</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:gap-4">
            <VerdictOption label="Approve" selected={editable ? verdict === 'CONFIRMED_PASS' : !rejected && detail.final_status === 'CONFIRMED_PASS'} disabled={!editable || saving} tone="pass" onClick={() => { setVerdict('CONFIRMED_PASS'); setMemoError(false); setError('') }} />
            <VerdictOption label="Reject" selected={editable ? verdict === 'CONFIRMED_REJECT' : rejected} disabled={!editable || saving} tone="reject" onClick={() => { setVerdict('CONFIRMED_REJECT'); setMemoError(false); setError('') }} />
          </div>
          <label className="mt-3 grid grid-cols-[40px_minmax(0,1fr)] items-center gap-1 text-xs text-secondary sm:grid-cols-[52px_minmax(0,1fr)] dark:text-dark-secondary">
            <span>Note{reasonRequired && <strong className="ml-1 text-danger dark:text-rose-300">*</strong>}</span>
            <input value={editable ? reason : detail.audit_logs.at(-1)?.reason ?? ''} onChange={event => { setReason(event.currentTarget.value); setMemoError(false) }} disabled={!editable || saving} required={reasonRequired} aria-invalid={memoError} placeholder={editable ? 'Enter a reason to update' : 'No admin verdict record'} className={`h-10 min-w-0 rounded-lg border bg-transparent px-3 text-ink placeholder:text-muted focus:outline-none dark:text-dark-ink dark:placeholder:text-dark-secondary ${memoError ? 'border-danger dark:border-rose-400' : 'border-line-soft focus:border-primary dark:border-dark-control'}`} />
          </label>
          {memoError && <p role="alert" className="mt-2 text-xs text-danger dark:text-rose-300">Please enter a reason for the update.</p>}
        </section>
      </div>
      <div className="mt-6 flex items-center justify-between gap-3">
        <Button tone="secondary" onClick={() => navigate('/admin/inspections')}>Back to List</Button>
        {editable && <Button onClick={requestSave}>{pending ? 'Confirm Verdict' : 'Update Verdict'}</Button>}
      </div>
    </>}
    {confirming && <div role="dialog" aria-modal="true" aria-label="Confirm verdict change" className="fixed inset-0 z-20 grid place-items-center bg-slate-950/60 p-4">
      <section className="w-full max-w-[660px] rounded-[20px] border border-line-soft bg-white p-5 text-center shadow-2xl sm:p-8 dark:border-dark-line dark:bg-dark-raised">
        <h2 className="text-xl font-bold sm:text-2xl">{verdict === 'CONFIRMED_PASS' ? 'Approve this inspection?' : 'Reject this inspection?'}</h2>
        <p className="mt-4 break-all text-secondary dark:text-dark-secondary">{inspectionId}</p>
        <div className="mt-8 flex justify-center gap-3"><Button tone="secondary" disabled={saving} onClick={() => setConfirming(false)}>Cancel</Button><Button disabled={saving} onClick={() => void save()}>{saving ? 'Saving…' : 'Confirm'}</Button></div>
      </section>
    </div>}
  </section>
}
