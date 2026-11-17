import type { ReactNode } from 'react'

export function AdminViewport({ children }: { readonly children: ReactNode }) {
  return <div data-admin-viewport className="grid min-h-[100dvh] min-w-[1440px] place-items-center bg-canvas dark:bg-[#0b1018]">{children}</div>
}
