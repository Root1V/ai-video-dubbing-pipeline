import { useEffect, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { Loader2, Pause, Play } from 'lucide-react'
import { playPreview, stopPreview } from '../../lib/audioPreview'
import { cn } from '../../lib/cn'

interface SamplePreviewButtonProps {
  /** Identificador unico de esta muestra (para que el singleton de
   * audioPreview sepa si ESTE boton es el que esta sonando ahora mismo). */
  sampleKey: string
  /** Resuelve la URL reproducible (blob autenticado u object URL local) --
   * solo se llama la primera vez que se hace play, y se cachea. */
  fetchUrl: () => Promise<string>
  className?: string
}

/** Boton compacto de play/pausa para escuchar un preview corto (voz o
 * musica) antes de elegirlo -- pensado para vivir dentro de una tarjeta de
 * opcion seleccionable, por eso detiene la propagacion del click (no debe
 * disparar tambien la seleccion de la tarjeta). */
export function SamplePreviewButton({ sampleKey, fetchUrl, className }: SamplePreviewButtonProps) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'playing'>('idle')
  const urlRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    }
  }, [])

  async function handleClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (status === 'playing') {
      stopPreview()
      setStatus('idle')
      return
    }
    setStatus('loading')
    try {
      if (!urlRef.current) {
        urlRef.current = await fetchUrl()
      }
      playPreview(sampleKey, urlRef.current, () => setStatus('idle'))
      setStatus('playing')
    } catch {
      setStatus('idle')
    }
  }

  const label = status === 'playing' ? 'Pausar preview' : 'Reproducir preview'

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={label}
      title={label}
      className={cn(
        'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border',
        'text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground',
        className,
      )}
    >
      {status === 'loading' && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      {status === 'playing' && <Pause className="h-3.5 w-3.5" />}
      {status === 'idle' && <Play className="h-3.5 w-3.5" />}
    </button>
  )
}
