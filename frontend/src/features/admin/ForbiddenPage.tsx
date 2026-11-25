import { ShieldAlert } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button, ThemeToggle } from '../../components/ui'
import { AdminViewport } from './AdminViewport'

export function ForbiddenPage() {
  const navigate = useNavigate()
  return <AdminViewport><main className="relative grid h-[900px] w-[1440px] place-items-center overflow-hidden rounded-[18px] border border-line bg-white text-center dark:border-dark-line dark:bg-dark-surface"><strong className="absolute left-8 top-7 text-lg text-primary">Rentaly</strong><div className="absolute right-8 top-6"><ThemeToggle /></div><section className="flex flex-col items-center"><ShieldAlert className="size-44 rounded-full bg-danger-soft p-14 text-danger dark:bg-rose-500/15" /><h1 className="mt-9 text-3xl font-bold">You do not have permission to access this page</h1><p className="mt-3 text-sm text-secondary dark:text-dark-secondary">Administrator privileges were not verified. Please go back or sign in with an administrator account.</p><div className="mt-14 flex gap-5"><Button tone="secondary" className="h-12 w-52" onClick={() => navigate(-1)}>Go Back</Button><Button className="h-12 w-52" onClick={() => navigate('/admin/login')}>Admin Login</Button></div></section></main></AdminViewport>
}
