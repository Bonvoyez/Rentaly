import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, Outlet, useNavigate, useParams } from 'react-router-dom'
import { HTTPError } from 'ky'
import { Button, ThemeToggle } from '../../components/ui'
import orbitImage from '../../assets/rentaly-orbit.png'
import { adminApi, clearSession, type InspectionDetail, type InspectionSummary } from '../../services/admin-api'
import { AdminViewport } from './AdminViewport'

function errorMessage(error: unknown): string {
  if (error instanceof HTTPError) {
    if (error.response.status === 401) return '아이디·비밀번호 또는 로그인 만료 여부를 확인해 주세요.'
    if (error.response.status === 403) return '관리자 권한이 필요합니다.'
    if (error.response.status === 409) return '이미 처리된 검사입니다. 새로고침 후 확인해 주세요.'
    return `요청을 처리하지 못했습니다 (${error.response.status}).`
  }
  return '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
}
function Alert({ children }: { readonly children: ReactNode }) { return <p role="alert" className="my-4 rounded-xl bg-danger-soft p-4 text-danger">{children}</p> }
const fieldClass = 'h-12 w-full rounded-xl border border-line-soft bg-transparent px-4 dark:border-slate-600'

export function LiveLogin() {
  const navigate = useNavigate()
  const [account, setAccount] = useState(''); const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    try { await adminApi.login(account, password); const user = await adminApi.me(); if (user.role !== 'ADMIN') { clearSession(); navigate('/admin/forbidden'); return }; navigate('/admin/inspections', { replace: true }) }
    catch (cause) { clearSession(); setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <AdminViewport><main className="grid h-[900px] w-[1440px] grid-cols-[560px_1fr] overflow-hidden rounded-[18px] border border-line bg-white dark:bg-[#121a26]">
    <section className="relative overflow-hidden bg-gradient-to-br from-blue-400 to-blue-700 p-14 text-white"><h1 className="text-2xl font-bold">반납검사</h1><p className="mt-6">검사 이력과 확인이 필요한 항목을<br />한곳에서 살펴볼 수 있어요.</p><img src={orbitImage} alt="" width="500" height="500" className="mt-20 w-full" /></section>
    <section className="relative grid place-items-center"><div className="absolute right-8 top-8"><ThemeToggle /></div><form onSubmit={submit} className="w-[500px]"><h2 className="text-3xl font-bold">관리자 로그인</h2><p className="mt-3 text-secondary">관리자 계정으로 로그인해 주세요.</p><label className="mt-12 grid gap-2">아이디<input className={fieldClass} autoComplete="username" required value={account} onChange={e => setAccount(e.currentTarget.value)} /></label><label className="mt-5 grid gap-2">비밀번호<input className={fieldClass} type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.currentTarget.value)} /></label>{error && <Alert>{error}</Alert>}<Button type="submit" disabled={busy} className="mt-8 w-full">{busy ? '로그인 중…' : '로그인'}</Button></form></section>
  </main></AdminViewport>
}

export function LiveShell() {
  const navigate = useNavigate(); const [account, setAccount] = useState<string>(); const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const expire = () => navigate('/admin/login?reason=expired', { replace: true })
    window.addEventListener('rentaly-session-expired', expire)
    void adminApi.me().then(user => { if (!active) return; if (user.role !== 'ADMIN') navigate('/admin/forbidden', { replace: true }); else setAccount(user.account) }).catch(cause => { if (active) setError(errorMessage(cause)) })
    return () => { active = false; window.removeEventListener('rentaly-session-expired', expire) }
  }, [navigate])
  if (!sessionStorage.getItem('rentaly-token')) return <Navigate to="/admin/login" replace />
  return <AdminViewport><div className="grid h-[900px] w-[1440px] grid-cols-[220px_minmax(0,1fr)] overflow-hidden rounded-[18px] border border-line bg-white dark:bg-[#121a26]"><aside className="flex flex-col gap-6 border-r border-line-soft p-6"><strong className="text-primary">반납검사</strong><span>{account}</span><Link to="/admin/inspections">검사 이력</Link><div className="mt-auto grid gap-4"><ThemeToggle /><button onClick={() => { clearSession(); navigate('/admin/login', { replace: true }) }}>로그아웃</button></div></aside><main className="overflow-y-auto p-10">{error ? <Alert>{error}<button onClick={() => window.location.reload()}>다시 시도</button></Alert> : account ? <Outlet /> : <p role="status">관리자 확인 중…</p>}</main></div></AdminViewport>
}

export function LiveInspections() {
  const [records, setRecords] = useState<readonly InspectionSummary[]>([]); const [page, setPage] = useState(0)
  const [busy, setBusy] = useState(true); const [error, setError] = useState(''); const [reload, setReload] = useState(0)
  useEffect(() => {
    let active = true
    void adminApi.list(page * 20).then(data => { if (active) { setRecords(data); setBusy(false) } }).catch(cause => { if (active) { setError(errorMessage(cause)); setBusy(false) } })
    return () => { active = false }
  }, [page, reload])
  function changePage(value: number) { setBusy(true); setError(''); setPage(value) }
  return <section><h1 className="text-[28px] font-bold">검사 이력</h1><p className="mt-3 text-secondary">최신 검사부터 페이지당 20건을 표시합니다.</p>{error && <Alert>{error}<button onClick={() => { setBusy(true); setError(''); setReload(value => value + 1) }}>다시 시도</button></Alert>}{busy ? <p role="status" className="mt-8">검사 이력을 불러오는 중…</p> : !error && <><div className="mt-8 overflow-hidden rounded-xl border border-line-soft"><table className="w-full text-left text-sm"><thead className="bg-canvas"><tr>{['검사 ID', '장비', '검사 시각', '고유번호', '상태', '작업'].map(label => <th key={label} className="p-4">{label}</th>)}</tr></thead><tbody>{records.map(record => <tr key={record.inspection_id} className="border-t border-line-soft"><td className="max-w-48 truncate p-4" title={record.inspection_id}>{record.inspection_id}</td><td>{record.equipment_id}</td><td>{new Date(record.inspected_at).toLocaleString('ko-KR')}</td><td>{record.recognized_serial_number || '—'}</td><td>{record.final_status}</td><td><Link className="text-primary" to={`/admin/inspections/${encodeURIComponent(record.inspection_id)}`}>상세 보기</Link></td></tr>)}</tbody></table></div>{records.length === 0 && <p className="p-8">검사 이력이 없습니다.</p>}<nav aria-label="검사 이력 페이지" className="mt-6 flex items-center justify-end gap-6"><Button disabled={page === 0} onClick={() => changePage(page - 1)}>이전</Button><span>{page + 1}페이지</span><Button disabled={records.length < 20} onClick={() => changePage(page + 1)}>다음</Button></nav></>}</section>
}

export function LiveDetail() {
  const { inspectionId = '' } = useParams()
  return <InspectionDetailView key={inspectionId} inspectionId={inspectionId} />
}

function InspectionDetailView({ inspectionId }: { readonly inspectionId: string }) {
  const [detail, setDetail] = useState<InspectionDetail>()
  const [error, setError] = useState(''); const [imageError, setImageError] = useState(''); const [image, setImage] = useState('')
  const [reason, setReason] = useState(''); const [decision, setDecision] = useState<'CONFIRMED_PASS' | 'CONFIRMED_REJECT'>('CONFIRMED_PASS')
  const [confirming, setConfirming] = useState(false); const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true; let url = ''
    void adminApi.detail(inspectionId).then(async data => {
      if (!active) return
      setDetail(data)
      const first = data.images[0]
      if (first) { try { const blob = await adminApi.image(first.image_id); if (active) { url = URL.createObjectURL(blob); setImage(url) } } catch (cause) { if (active) setImageError(errorMessage(cause)) } }
    }).catch(cause => { if (active) setError(errorMessage(cause)) })
    return () => { active = false; if (url) URL.revokeObjectURL(url) }
  }, [inspectionId])
  async function save() {
    setBusy(true); setError('')
    try { setDetail(await adminApi.confirm(inspectionId, decision, reason)); setConfirming(false) }
    catch (cause) { setError(errorMessage(cause)); setConfirming(false) }
    finally { setBusy(false) }
  }
  return <section><h1 className="text-[28px] font-bold">검사 상세</h1><p className="mt-3 text-secondary">검사 ID · {inspectionId}</p>{error && <Alert>{error}</Alert>}{!detail ? <p role="status">{error ? '상세 정보를 불러오지 못했습니다.' : '불러오는 중…'}</p> : <><div className="mt-8 grid grid-cols-2 gap-7"><section className="rounded-2xl border border-line-soft p-5">{image ? <img src={image} alt="검사 중 촬영된 보드" className="h-80 w-full object-contain" /> : <p className="grid h-80 place-items-center">{imageError || (detail.images.length ? '이미지를 불러오는 중…' : '촬영 이미지 없음')}</p>}</section><section className="rounded-2xl border border-line-soft p-5"><h2 className="text-lg font-bold">검사 정보</h2><dl className="mt-5 grid grid-cols-2 gap-5">{[['장비', detail.equipment_id], ['검사 시각', new Date(detail.inspected_at).toLocaleString('ko-KR')], ['고유번호', detail.recognized_serial_number || '—'], ['AI 판정', detail.primary_verdict], ['최종 상태', detail.final_status], ['전원 표시등', detail.ai_result ? detail.ai_result.pwr_led_status ? '점등' : '꺼짐' : '미수행'], ['결함', detail.ai_result ? JSON.stringify(detail.ai_result.detected_defects ?? []) : '미수행']].map(([label, value]) => <div className="contents" key={label}><dt className="text-secondary">{label}</dt><dd className="break-words">{value}</dd></div>)}</dl></section></div>{detail.final_status === 'PENDING_REVIEW' && <section className="mt-8 rounded-2xl border border-line-soft p-5"><h2 className="text-lg font-bold">관리자 최종 판정</h2><label className="mt-5 grid gap-2">판정<select className={fieldClass} value={decision} onChange={e => setDecision(e.currentTarget.value === 'CONFIRMED_PASS' ? 'CONFIRMED_PASS' : 'CONFIRMED_REJECT')}><option value="CONFIRMED_PASS">승인</option><option value="CONFIRMED_REJECT">반려</option></select></label><label className="mt-5 grid gap-2">판정 사유<input className={fieldClass} value={reason} onChange={e => setReason(e.currentTarget.value)} /></label><Button className="mt-5" onClick={() => setConfirming(true)}>판정 확정</Button></section>}<section className="mt-8"><h2 className="text-lg font-bold">처리 이력</h2>{detail.audit_logs.length === 0 ? <p className="mt-3">처리 이력이 없습니다.</p> : detail.audit_logs.map(log => <p className="mt-3" key={log.audit_id}>{new Date(log.created_at).toLocaleString('ko-KR')} · {log.action} · {log.reason}</p>)}</section></>}{confirming && <div role="dialog" aria-modal="true" aria-label="판정 확정 확인" className="fixed inset-0 z-50 grid place-items-center bg-black/40"><div className="rounded-2xl bg-white p-8 dark:bg-slate-800"><h2 className="text-xl font-bold">{decision === 'CONFIRMED_PASS' ? '승인' : '반려'} 판정을 저장할까요?</h2><div className="mt-6 flex gap-4"><Button disabled={busy} onClick={() => setConfirming(false)}>취소</Button><Button disabled={busy} onClick={() => void save()}>{busy ? '저장 중…' : '저장'}</Button></div></div></div>}<Link className="mt-8 inline-block text-primary" to="/admin/inspections">목록으로</Link></section>
}
