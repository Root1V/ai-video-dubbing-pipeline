import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '../../lib/cn'

export type AlertVariant = 'error' | 'success' | 'info'

export interface AlertProps {
  variant?: AlertVariant
  children: ReactNode
  onDismiss?: () => void
  className?: string
}

const variantClasses: Record<AlertVariant, string> = {
  error: 'bg-destructive/10 text-destructive border-destructive/20',
  success: 'bg-success/10 text-success border-success/20',
  info: 'bg-primary/10 text-primary border-primary/20',
}

export function Alert({ variant = 'info', children, onDismiss, className }: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm',
        variantClasses[variant],
        className,
      )}
    >
      <div>{children}</div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Cerrar"
          className="shrink-0 rounded-md p-0.5 hover:bg-black/5"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
