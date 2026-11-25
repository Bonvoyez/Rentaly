import type { ReactNode } from 'react'

export function AdminViewport({ children }: { readonly children: ReactNode }) {
  return <div data-admin-viewport className="grid min-h-[100dvh] min-w-0 place-items-center bg-canvas p-4 dark:bg-dark-canvas">{children}</div>
}
