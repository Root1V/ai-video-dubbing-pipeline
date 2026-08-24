import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { fetchMediaPreview } from '../../api/media'
import type { MediaPreview } from '../../types/media'
import { formatClockTime } from '../../lib/format'

const DEBOUNCE_MS = 600

interface MediaUrlPreviewProps {
  url: string
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
 * Previsualiza una URL pegada por el usuario antes de confirmar la descarga:
 * reproductor embebido oficial de YouTube si aplica, o una tarjeta con
 * miniatura/titulo/duracion para el resto. No bloquea el envio del
 * formulario si falla -- la validacion real ocurre en el backend al
 * descargar (ver web/services/media_import.py).
 */
export function MediaUrlPreview({ url }: MediaUrlPreviewProps) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [preview, setPreview] = useState<MediaPreview | null>(null)

  useEffect(() => {
    if (!isLikelyUrl(url)) {
      setStatus('idle')
      setPreview(null)
      return
    }
    setStatus('loading')
    const timer = window.setTimeout(() => {
      fetchMediaPreview(url)
        .then((result) => {
          setPreview(result)
          setStatus('success')
        })
        .catch(() => {
          setStatus('error')
        })
    }, DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [url])

  if (status === 'idle') return null

  if (status === 'loading') {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-border bg-secondary/30 p-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Cargando previsualización…
      </div>
    )
  }

  if (status === 'error') {
    return (
      <p className="text-xs text-muted-foreground">
        No se pudo previsualizar esa URL, pero igual puedes continuar.
      </p>
    )
  }

  if (!preview) return null

  if (preview.is_youtube && preview.youtube_video_id) {
    return (
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
    )
  }

  return (
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
  )
}
