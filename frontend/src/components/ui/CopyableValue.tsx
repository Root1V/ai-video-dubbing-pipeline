import { useState } from 'react'
import type { MouseEvent } from 'react'
import { Check, Copy } from 'lucide-react'
import { cn } from '../../lib/cn'

interface CopyableValueProps {
  value: string
  className?: string
}

/** A value (e.g. a run ID) with a small copy-to-clipboard button next to it.
 * Stops propagation so it can be dropped inside a clickable table row
 * without also triggering the row's own onClick (navigation). */
export function CopyableValue({ value, className }: CopyableValueProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation()
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard API can be unavailable (permissions, insecure context) --
      // nothing sensible to recover, just leave the icon as "not copied".
    }
  }

  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <span>{value}</span>
      <button
        type="button"
        onClick={handleCopy}
        className="text-muted-foreground/70 transition-colors hover:text-foreground"
        aria-label="Copiar"
        title="Copiar"
      >
        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
      </button>
    </span>
  )
}
