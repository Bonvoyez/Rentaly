import { Check, CircleAlert, CircleCheck, CircleX, Moon, Sun } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { useTheme } from './theme-context'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { readonly tone?: 'primary' | 'secondary'; readonly size?: 'admin' | 'kiosk' }

export function Button({ tone = 'primary', size = 'admin', className = '', ...props }: ButtonProps) {
  const toneClass = tone === 'primary' ? 'border-transparent bg-primary text-white hover:bg-primary-hover' : 'border-line-soft bg-white text-ink hover:bg-slate-50 dark:border-dark-control dark:bg-dark-raised dark:text-dark-ink dark:hover:bg-dark-hover'
  const sizeClass = size === 'kiosk' ? 'min-h-14 w-60 rounded-[14px] text-base' : 'min-h-10 px-6'
  return <button className={`cursor-pointer rounded-xl border font-bold transition-colors disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 dark:disabled:bg-dark-line dark:disabled:text-dark-secondary ${toneClass} ${sizeClass} ${className}`} {...props} />
}

export type StatusTone = 'success' | 'warning' | 'error' | 'neutral'
const badgeClasses: Readonly<Record<StatusTone, string>> = {
  success: 'bg-success-soft text-success dark:bg-emerald-400/12 dark:text-emerald-300', warning: 'bg-warning-soft text-warning dark:bg-amber-400/12 dark:text-amber-300', error: 'bg-danger-soft text-danger dark:bg-rose-400/12 dark:text-rose-300', neutral: 'bg-slate-100 text-secondary dark:bg-dark-hover dark:text-dark-secondary',
}

export function StatusBadge({ tone, children }: { readonly tone: StatusTone; readonly children: ReactNode }) {
  return <span className={`inline-flex h-7 min-w-[106px] items-center justify-center rounded-full px-3 text-xs font-semibold ${badgeClasses[tone]}`}>{children}</span>
}

export function ThemeToggle({ compact = false, className = '' }: { readonly compact?: boolean; readonly className?: string }) {
  const { theme, toggleTheme } = useTheme()
  const dark = theme === 'dark'
  return <button type="button" onClick={toggleTheme} aria-label={dark ? '라이트 모드로 전환' : '다크 모드로 전환'} className={`inline-flex min-h-10 items-center gap-2 rounded-xl border border-line-soft bg-white px-3 text-xs font-semibold text-secondary hover:bg-slate-50 dark:border-dark-control dark:bg-dark-raised dark:text-dark-secondary dark:hover:bg-dark-hover ${className}`}>{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}{compact ? null : dark ? '라이트' : '다크'}</button>
}

export function SystemStatus({ connected = true, label }: { readonly connected?: boolean; readonly label?: string }) {
  return <div className={`absolute right-6 top-5 flex h-9 min-w-35 items-center gap-2.5 rounded-[14px] px-3.5 text-[13px] font-medium ${connected ? 'bg-success-soft text-success dark:bg-emerald-500/15 dark:text-emerald-300' : 'bg-danger-soft text-danger dark:bg-rose-500/15 dark:text-rose-300'}`}><span className={`size-2.5 rounded-full ${connected ? 'bg-success' : 'bg-danger'}`} />{label ?? (connected ? '정상 연결' : '연결 실패')}</div>
}

export function ProgressBar({ value, label }: { readonly value: number; readonly label?: string }) {
  return <div className="absolute bottom-7 left-6 right-12"><div className="h-2.5 overflow-hidden rounded-full bg-line-soft dark:bg-slate-700" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><span className="block h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${value}%` }} /></div>{label ? <span className="absolute right-0 top-3.5 translate-x-6 text-xs font-semibold text-primary">{label}</span> : null}</div>
}

export type CheckTone = 'success' | 'active' | 'warning' | 'error' | 'muted'
const checkClasses: Readonly<Record<CheckTone, string>> = {
  success: 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/35 dark:bg-emerald-400/10 dark:text-emerald-300', active: 'border-line-soft bg-white text-ink dark:border-dark-control dark:bg-dark-surface dark:text-dark-ink', warning: 'border-warning bg-amber-50 text-amber-700 dark:border-amber-500/35 dark:bg-amber-400/10 dark:text-amber-300', error: 'border-danger bg-rose-50 text-rose-700 dark:border-rose-500/35 dark:bg-rose-400/10 dark:text-rose-300', muted: 'border-line-soft bg-white text-muted dark:border-dark-line dark:bg-dark-surface dark:text-dark-secondary',
}

export function InspectionCheck({ label, state, tone, compact = false }: { readonly label: string; readonly state: string; readonly tone: CheckTone; readonly compact?: boolean }) {
  const icon = tone === 'success' ? <Check className="size-4" /> : tone === 'warning' ? <CircleAlert className="size-4" /> : tone === 'error' ? <CircleX className="size-4" /> : tone === 'active' ? <span className="size-[18px] rounded-full bg-primary" /> : <span>•</span>
  return <div className={`grid ${compact ? 'h-10' : 'h-12'} grid-cols-[28px_1fr_auto] items-center gap-0.5 rounded-xl border px-3 text-[13px] ${checkClasses[tone]}`}><span className="grid w-5 place-items-center">{icon}</span><span>{label}</span><strong className={`text-[11px] font-medium ${tone === 'active' ? 'text-primary' : ''}`}>{state}</strong></div>
}

export function ConfirmDialog({ verdict, onCancel, onConfirm }: { readonly verdict: 'pass' | 'reject'; readonly onCancel: () => void; readonly onConfirm: () => void }) {
  const pass = verdict === 'pass'
  return <dialog open onCancel={onCancel} className="fixed inset-0 z-20 m-0 grid h-full max-h-none w-full max-w-none place-items-center border-0 bg-slate-950/35 pl-[220px]"><section className="min-h-[430px] w-[660px] rounded-[20px] border border-line-soft bg-white px-12 pb-8 pt-8 text-center shadow-2xl dark:border-[#334155] dark:bg-[#121a26]"><div className={`mx-auto mb-5 grid size-[88px] place-items-center rounded-full ${pass ? 'bg-success-soft text-success dark:bg-emerald-500/15' : 'bg-warning-soft text-warning dark:bg-amber-500/15'}`}>{pass ? <CircleCheck className="size-10" /> : <CircleAlert className="size-10" />}</div><h2 className="text-2xl font-bold">이 검사를 {pass ? '승인' : '반려'}하시겠어요?</h2><p className="mb-8 mt-4 text-[13px] text-secondary dark:text-slate-400">확정하면 검사 이력에 반영됩니다.</p><div className={`grid h-[76px] grid-cols-2 items-center rounded-[14px] px-11 text-left ${pass ? 'bg-success-soft text-success dark:bg-emerald-500/10' : 'bg-amber-50 text-warning dark:bg-amber-500/10'}`}><strong>{pass ? '승인' : '반려'}</strong><span className="text-[13px] text-secondary dark:text-slate-300">7b2c4d91...1b90</span></div><div className="mt-7 grid grid-cols-[250px_300px] gap-2.5"><Button tone="secondary" className="h-12" onClick={onCancel}>취소</Button><Button className="h-12" onClick={onConfirm}>확정하고 목록으로</Button></div></section></dialog>
}
