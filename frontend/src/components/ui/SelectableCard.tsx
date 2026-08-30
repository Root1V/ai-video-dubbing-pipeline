import type { KeyboardEvent, ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface SelectableCardProps {
  selected: boolean
  onSelect: () => void
  children: ReactNode
  className?: string
}

/** Tarjeta seleccionable accesible por teclado, usando `<div role="button">`
 * en vez de un `<button>` real -- necesario cuando el contenido incluye otro
 * control interactivo (p.ej. SamplePreviewButton): anidar `<button>` dentro
 * de `<button>` es HTML invalido, el navegador reordena el DOM y rompe el
 * layout/comportamiento de click del control interno. */
export function SelectableCard({ selected, onSelect, children, className }: SelectableCardProps) {
  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      className={cn(
        'flex cursor-pointer flex-col items-start gap-0.5 rounded-xl border p-3 text-left transition-colors',
        selected ? 'border-primary bg-primary/5' : 'border-border hover:bg-secondary/50',
        className,
      )}
    >
      {children}
    </div>
  )
}
