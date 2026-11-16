import { ClipboardList, LogOut, MonitorCog } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ThemeToggle } from '../../components/ui'

const navClass = ({ isActive }: { readonly isActive: boolean }) => `flex h-11 items-center gap-3 rounded-xl px-4 text-sm transition-colors ${isActive ? 'bg-primary-soft font-semibold text-primary dark:bg-primary/15' : 'text-secondary hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}`

export function AdminShell() {
  const navigate = useNavigate()
  return <div className="mx-auto grid h-[900px] w-[1440px] grid-cols-[220px_minmax(0,1fr)] overflow-hidden rounded-[18px] border border-line bg-white dark:border-[#273446] dark:bg-[#121a26]"><aside className="relative h-full bg-[#fbfcfd] px-3.5 py-6 dark:bg-[#0f1722]"><div className="ml-2 text-lg font-bold text-primary">반납검사</div><span className="mb-8 ml-2 mt-0.5 block text-xs text-muted">admin0301 · Mock</span><nav aria-label="관리자 메뉴" className="grid gap-1"><NavLink className={navClass} to="/admin/inspections"><ClipboardList className="size-4" />검사 이력</NavLink><NavLink className={navClass} to="/admin/devices"><MonitorCog className="size-4" />장비 관리</NavLink></nav><div className="absolute bottom-6 left-5 right-5 grid gap-2"><ThemeToggle /><button type="button" onClick={() => navigate('/admin/login')} className="flex min-h-10 items-center gap-2 px-2 text-xs text-muted hover:text-danger"><LogOut className="size-4" />로그아웃</button></div></aside><main className="min-h-0 overflow-y-auto bg-white dark:bg-[#121a26]"><Outlet /></main></div>
}
