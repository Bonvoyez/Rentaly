import { ShieldAlert } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button, ThemeToggle } from '../../components/ui'
import { AdminViewport } from './AdminViewport'

export function ForbiddenPage() {
  const navigate = useNavigate()
  return <AdminViewport><main className="relative grid h-[900px] w-[1440px] place-items-center overflow-hidden rounded-[18px] border border-line bg-white text-center dark:border-[#273446] dark:bg-[#121a26]"><strong className="absolute left-8 top-7 text-lg text-primary">반납검사</strong><div className="absolute right-8 top-6"><ThemeToggle /></div><section className="flex flex-col items-center"><ShieldAlert className="size-44 rounded-full bg-danger-soft p-14 text-danger dark:bg-rose-500/15" /><h1 className="mt-9 text-3xl font-bold">이 페이지에 접근할 권한이 없어요</h1><p className="mt-3 text-sm text-secondary dark:text-slate-400">관리자 권한이 확인되지 않았습니다. 이전 화면으로 돌아가거나 관리자 계정으로 로그인해 주세요.</p><div className="mt-14 flex gap-5"><Button tone="secondary" className="h-12 w-52" onClick={() => navigate(-1)}>이전 화면</Button><Button className="h-12 w-52" onClick={() => navigate('/admin/login')}>관리자 로그인</Button></div></section></main></AdminViewport>
}
