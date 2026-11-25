import { useEffect, useState } from 'react'
import { ClipboardList, LogOut, MonitorCog } from 'lucide-react'
import { Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ThemeToggle } from '../../components/ui'
import { adminApi, clearSession } from '../../services/admin-api'

const navClass = ({ isActive }: { readonly isActive: boolean }) =>
  `flex h-11 min-w-0 items-center justify-center gap-2 rounded-xl px-2 text-sm transition-colors md:justify-start md:gap-3 md:px-4 ${isActive
    ? 'bg-primary-soft font-semibold text-primary dark:bg-dark-selected dark:text-dark-accent'
    : 'text-secondary hover:bg-slate-100 dark:text-dark-secondary dark:hover:bg-dark-hover'}`

export function AdminShell({ live = false }: { readonly live?: boolean }) {
  const navigate = useNavigate()
  const [account, setAccount] = useState<string>()
  const [error, setError] = useState('')

  useEffect(() => {
    if (!live) return
    let active = true
    const expire = () => navigate('/admin/login?reason=expired', { replace: true })
    window.addEventListener('rentaly-session-expired', expire)
    void adminApi.me().then(user => {
      if (active) {
        if (user.role === 'ADMIN') setAccount(user.account)
        else navigate('/admin/forbidden', { replace: true })
      }
    }).catch(() => { if (active) setError('관리자 정보를 확인하지 못했습니다. 다시 로그인해 주세요.') })
    return () => { active = false; window.removeEventListener('rentaly-session-expired', expire) }
  }, [live, navigate])

  if (live && !sessionStorage.getItem('rentaly-token')) return <Navigate to="/admin/login" replace />

  return <div className="min-h-[100dvh] bg-canvas p-2 sm:p-4 dark:bg-dark-canvas">
    <div className="mx-auto grid min-h-[calc(100dvh-1rem)] w-full max-w-[1440px] overflow-hidden rounded-[18px] border border-line bg-white sm:min-h-[calc(100dvh-2rem)] md:grid-cols-[220px_minmax(0,1fr)] dark:border-dark-line dark:bg-dark-surface">
      <aside className="grid grid-cols-2 gap-2 border-b border-line-soft bg-[#fbfcfd] p-3 sm:p-5 md:flex md:flex-col md:items-stretch md:gap-0 md:border-b-0 md:border-r dark:border-dark-line dark:bg-dark-sidebar">
        <div className="col-span-2 flex min-w-0 items-baseline justify-between gap-2 md:block">
          <span className="shrink-0 text-lg font-bold text-primary dark:text-dark-accent">반납검사</span>
          <span className="truncate text-right text-xs text-muted md:mb-8 md:mt-1 md:block md:text-left dark:text-dark-secondary">{live ? `${account ?? '관리자 확인 중…'} · 관리자` : 'admin0301 · Mock'}</span>
        </div>
        <nav aria-label="관리자 메뉴" className="col-span-2 grid grid-cols-2 gap-2 md:grid-cols-1 md:gap-1">
          <NavLink className={navClass} to="/admin/inspections"><ClipboardList className="size-4 shrink-0" />검사 이력</NavLink>
          <NavLink className={navClass} to="/admin/devices"><MonitorCog className="size-4 shrink-0" />장비 관리</NavLink>
        </nav>
        <div className="col-span-2 grid grid-cols-2 gap-2 md:mt-auto md:grid-cols-1 md:gap-1">
          <ThemeToggle className="w-full justify-center md:justify-start" />
          <button type="button" onClick={() => { if (live) clearSession(); navigate('/admin/login') }} className="flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-line-soft px-2 text-xs text-secondary hover:bg-slate-100 hover:text-danger md:justify-start md:border-transparent dark:border-dark-control dark:text-dark-secondary dark:hover:bg-dark-hover dark:hover:text-rose-300"><LogOut className="size-4" />로그아웃</button>
        </div>
      </aside>
      <main className="min-w-0 overflow-y-auto bg-white dark:bg-dark-surface">
        {error ? <p role="alert" className="p-10 text-danger dark:text-rose-300">{error}</p> : live && !account ? <p role="status" className="p-10">관리자 확인 중…</p> : <Outlet />}
      </main>
    </div>
  </div>
}
