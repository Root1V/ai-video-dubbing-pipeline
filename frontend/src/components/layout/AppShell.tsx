import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { cn } from '../../lib/cn'

interface AppShellProps {
  children: ReactNode
  /** true = la pagina maneja su propio padding/scroll (p.ej. un layout de
   * editor a pantalla completa) -- ver NewMicroVideoProjectPage.tsx. */
  fullBleed?: boolean
}

export function AppShell({ children, fullBleed }: AppShellProps) {
  return (
    <div className="flex h-screen w-full bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className={cn('flex-1', fullBleed ? 'overflow-hidden' : 'overflow-y-auto p-6')}>
          {children}
        </main>
      </div>
    </div>
  )
}
