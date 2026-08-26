import { useEffect, useState } from 'react'
import { Loader2, ShieldCheck, ShieldQuestion } from 'lucide-react'
import { fetchMediaPreview } from '../../api/media'
import type { MediaPreview } from '../../types/media'
import { Button } from '../ui/Button'
import { formatClockTime } from '../../lib/format'

const DEBOUNCE_MS = 600

interface MediaUrlPreviewProps {
  url: string
  /** Se llama con `true` en cuanto la URL se confirma alcanzable/descargable
   * (automatico o via el boton "Validar URL"), y con `false` cada vez que
   * cambia a una URL todavia no confirmada -- el formulario que envuelve a
   * este componente usa esto para no dejar enviar hasta tener una
   * confirmacion real, en vez de asumir que cualquier URL escrita sirve. */
  onValidatedChange: (validated: boolean) => void
}

function isLikelyUrl(value: string): boolean {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

/**
 * Previsualiza una URL pegada por el usuario: reproductor embebido oficial
 * de YouTube si aplica, o una tarjeta con miniatura/titulo/duracion para el
 * resto. Ademas de mostrar la previsualizacion, esta es la validacion real
 * de que la URL es alcanzable/descargable (reusa GET /media/preview, que ya
 * hace la misma extraccion que el backend usaria para descargar) -- si el
 * intento automatico falla, se ofrece un boton para reintentar a mano en
 * vez de dejar pasar la URL sin confirmar.
 */
export function MediaUrlPreview({ url, onValidatedChange }: MediaUrlPreviewProps) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [preview, setPreview] = useState<MediaPreview | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!isLikelyUrl(url)) {
      setStatus('idle')
      setPreview(null)
      onValidatedChange(false)
      return
    }
    setStatus('loading')
    onValidatedChange(false)
    // Sin debounce en un reintento manual (retryCount > 0) -- el usuario ya
    // hizo clic en "Validar URL", no hace falta esperar a que "deje de
    // escribir" porque no esta escribiendo.
    const delay = retryCount === 0 ? DEBOUNCE_MS : 0
    const timer = window.setTimeout(() => {
      fetchMediaPreview(url)
        .then((result) => {
          setPreview(result)
          setStatus('success')
          onValidatedChange(true)
        })
        .catch(() => {
          setStatus('error')
          onValidatedChange(false)
        })
    }, delay)
    return () => window.clearTimeout(timer)
    // onValidatedChange se omite a proposito: es una funcion nueva en cada
    // render del padre, incluirla dispararia este efecto sin que la URL
    // realmente haya cambiado.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, retryCount])

  if (status === 'idle') return null

  if (status === 'loading') {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-border bg-secondary/30 p-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Validando URL…
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="flex items-center justify-between gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-3">
        <div className="flex items-center gap-2 text-sm text-destructive">
          <ShieldQuestion className="h-4 w-4 shrink-0" />
          No se pudo validar esa URL. Verifica que sea correcta e intenta de nuevo.
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setRetryCount((n) => n + 1)}
        >
          Validar URL
        </Button>
      </div>
    )
  }

  if (!preview) return null

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-success">
        <ShieldCheck className="h-3.5 w-3.5" />
        URL validada
      </div>
      {preview.is_youtube && preview.youtube_video_id ? (
        <div className="flex flex-col gap-2">
          <div className="aspect-video w-full overflow-hidden rounded-xl border border-border">
            <iframe
              className="h-full w-full"
              src={`https://www.youtube.com/embed/${preview.youtube_video_id}`}
              title={preview.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          </div>
          <p className="truncate text-sm font-medium">{preview.title}</p>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-secondary/30 p-3">
          {preview.thumbnail_url && (
            <img
              src={preview.thumbnail_url}
              alt=""
              className="h-14 w-24 shrink-0 rounded-lg object-cover"
            />
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{preview.title}</p>
            {preview.duration_seconds !== null && (
              <p className="text-xs text-muted-foreground">
                {formatClockTime(preview.duration_seconds)}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
