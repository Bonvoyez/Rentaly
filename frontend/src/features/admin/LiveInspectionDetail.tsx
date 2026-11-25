import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, InspectionCheck, StatusBadge } from '../../components/ui'
import { adminApi, type InspectionDetail } from '../../services/admin-api'
import { VerdictOption } from './InspectionDetailPage'

type Verdict = 'CONFIRMED_PASS' | 'CONFIRMED_REJECT'

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
      setVerdict(result.final_status.includes('REJECT') ? 'CONFIRMED_REJECT' : 'CONFIRMED_PASS')
      const image = result.images[0]
      if (image) {
        try {
          const blob = await adminApi.image(image.image_id)
          if (active) { objectUrl = URL.createObjectURL(blob); setImageUrl(objectUrl) }
        } catch { if (active) setError('검사 이미지를 불러오지 못했습니다.') }
      }
    }).catch(() => { if (active) setError('검사 상세를 불러오지 못했습니다.') })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [inspectionId])

  const pending = detail?.final_status === 'PENDING_REVIEW'
  const passed = detail?.final_status === 'PASS' || detail?.final_status === 'CONFIRMED_PASS'
  const rejected = detail?.final_status.includes('REJECT') ?? false
  const editable = pending || passed || rejected
  const savedVerdict: Verdict = rejected ? 'CONFIRMED_REJECT' : 'CONFIRMED_PASS'
  const reasonRequired = editable && verdict !== savedVerdict
  const led = detail?.ai_result?.pwr_led_status
  const defects = detail?.ai_result?.detected_defects
  const defectsFound = Array.isArray(defects) && defects.length > 0

  function requestSave() {
    if (!pending && verdict === savedVerdict) {
      setError('변경할 판정을 선택해 주세요.')
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
      setVerdict(updated.final_status.includes('REJECT') ? 'CONFIRMED_REJECT' : 'CONFIRMED_PASS')
      setReason('')
      setConfirming(false)
    } catch {
      setError('판정을 저장하지 못했습니다. 검사 상태와 사유를 확인해 주세요.')
      setConfirming(false)
    } finally { setSaving(false) }
  }

  return <section className="min-h-full px-4 pb-8 pt-6 sm:px-6 md:px-10 md:pb-10 md:pt-8">
    <h1 className="text-[28px] font-bold tracking-tight">검사 상세</h1>
    <p className="mt-3 break-all text-[13px] text-secondary">검사 ID · {inspectionId}</p>
    {error && <p role="alert" className="mt-5 text-danger dark:text-rose-300">{error}</p>}
    {!detail ? <p role="status" className="mt-8">{error || '검사 정보를 불러오는 중…'}</p> : <>
      <div className="mt-6 grid gap-4 md:mt-8 md:gap-7 lg:grid-cols-2">
        <section className="min-w-0 rounded-2xl border border-line-soft bg-slate-50 p-3 sm:p-4 lg:h-[420px] dark:border-dark-line dark:bg-dark-raised">
          <div className="grid aspect-[4/3] max-h-[324px] place-items-center overflow-hidden rounded-xl bg-slate-200 text-muted dark:bg-dark-canvas">
            {imageUrl ? <img src={imageUrl} alt="검사 중 촬영된 Raspberry Pi 보드" className="h-full w-full object-contain" /> : '촬영 이미지 없음'}
          </div>
          <p className="mt-4 text-xs text-secondary lg:mt-5 dark:text-dark-secondary">보드 촬영 이미지</p>
        </section>
        <section className="min-w-0 rounded-2xl border border-line-soft p-4 sm:p-5 lg:h-[420px] dark:border-dark-line dark:bg-dark-raised">
          <h2 className="text-[17px] font-bold">검사 정보</h2>
          <dl className="mt-5 grid grid-cols-[minmax(92px,38%)_1fr] gap-y-4 text-xs sm:gap-y-5">
            {[
              ['검사 대상', detail.equipment_id],
              ['검사 시각', new Date(detail.inspected_at).toLocaleString('ko-KR')],
              ['고유번호', detail.recognized_serial_number || '—'],
              ['전원 표시등', led === undefined ? '미수행' : led ? '정상' : '확인 필요'],
              ['외관', !detail.ai_result ? '미수행' : defectsFound ? '확인 필요' : '정상'],
              ['검사 소요 시간', detail.total_duration_ms == null ? '—' : `${(detail.total_duration_ms / 1000).toFixed(1)}초`],
            ].map(([label, value]) => <div key={label} className="contents"><dt className="text-secondary dark:text-dark-secondary">{label}</dt><dd className="min-w-0 break-words font-semibold">{value}</dd></div>)}
            <dt className="text-secondary dark:text-dark-secondary">상태</dt>
            <dd><StatusBadge tone={pending || rejected ? 'warning' : detail.final_status === 'ERROR' ? 'error' : 'success'}>{detail.final_status}</StatusBadge></dd>
          </dl>
        </section>
        <section className="grid min-w-0 gap-2.5 rounded-2xl border border-line-soft p-4 lg:min-h-[210px] dark:border-dark-line dark:bg-dark-raised" aria-label="판정 결과">
          <InspectionCheck label="PWR LED 점등" state={led === undefined ? '미수행' : led ? '정상' : '확인 필요'} tone={led === undefined ? 'muted' : led ? 'success' : 'warning'} />
          <InspectionCheck label="외관 검사" state={!detail.ai_result ? '미수행' : defectsFound ? '확인 필요' : '정상'} tone={!detail.ai_result ? 'muted' : defectsFound ? 'warning' : 'success'} />
          <InspectionCheck label="고유번호 인식" state={detail.recognized_serial_number ? '완료' : '미인식'} tone={detail.recognized_serial_number ? 'success' : 'muted'} />
        </section>
        <section className="min-w-0 rounded-2xl border border-line-soft p-4 lg:min-h-[210px] dark:border-dark-line dark:bg-dark-raised">
          <h2 className="text-[17px] font-bold">관리자 최종 판정</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:gap-4">
            <VerdictOption label="승인" selected={editable ? verdict === 'CONFIRMED_PASS' : !rejected && detail.final_status === 'CONFIRMED_PASS'} disabled={!editable || saving} tone="pass" onClick={() => { setVerdict('CONFIRMED_PASS'); setMemoError(false); setError('') }} />
            <VerdictOption label="반려" selected={editable ? verdict === 'CONFIRMED_REJECT' : rejected} disabled={!editable || saving} tone="reject" onClick={() => { setVerdict('CONFIRMED_REJECT'); setMemoError(false); setError('') }} />
          </div>
          <label className="mt-3 grid grid-cols-[40px_minmax(0,1fr)] items-center gap-1 text-xs text-secondary sm:grid-cols-[52px_minmax(0,1fr)] dark:text-dark-secondary">
            <span>메모{reasonRequired && <strong className="ml-1 text-danger dark:text-rose-300">*</strong>}</span>
            <input value={editable ? reason : detail.audit_logs.at(-1)?.reason ?? ''} onChange={event => { setReason(event.currentTarget.value); setMemoError(false) }} disabled={!editable || saving} required={reasonRequired} aria-invalid={memoError} placeholder={editable ? '수정하려면 사유를 입력해주세요' : '관리자 판정 기록 없음'} className={`h-10 min-w-0 rounded-lg border bg-transparent px-3 text-ink placeholder:text-muted focus:outline-none dark:text-dark-ink dark:placeholder:text-dark-secondary ${memoError ? 'border-danger dark:border-rose-400' : 'border-line-soft focus:border-primary dark:border-dark-control'}`} />
          </label>
          {memoError && <p role="alert" className="mt-2 text-xs text-danger dark:text-rose-300">수정 사유를 입력해 주세요.</p>}
        </section>
      </div>
      <div className="mt-6 flex items-center justify-between gap-3">
        <Button tone="secondary" onClick={() => navigate('/admin/inspections')}>목록으로</Button>
        {editable && <Button onClick={requestSave}>{pending ? '판정 확정' : '판정 수정'}</Button>}
      </div>
    </>}
    {confirming && <div role="dialog" aria-modal="true" aria-label="판정 변경 확인" className="fixed inset-0 z-20 grid place-items-center bg-slate-950/60 p-4">
      <section className="w-full max-w-[660px] rounded-[20px] border border-line-soft bg-white p-5 text-center shadow-2xl sm:p-8 dark:border-dark-line dark:bg-dark-raised">
        <h2 className="text-xl font-bold sm:text-2xl">이 검사를 {verdict === 'CONFIRMED_PASS' ? '승인' : '반려'}하시겠어요?</h2>
        <p className="mt-4 break-all text-secondary dark:text-dark-secondary">{inspectionId}</p>
        <div className="mt-8 flex justify-center gap-3"><Button tone="secondary" disabled={saving} onClick={() => setConfirming(false)}>취소</Button><Button disabled={saving} onClick={() => void save()}>{saving ? '저장 중…' : '확정'}</Button></div>
      </section>
    </div>}
  </section>
}
