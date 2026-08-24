import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Loader2, Search } from 'lucide-react'
import { searchYoutubeVideos } from '../../api/media'
import type { MediaPreview } from '../../types/media'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { formatClockTime } from '../../lib/format'

interface YoutubeSearchPanelProps {
  onSelect: (sourceUrl: string) => void
}

/**
 * Busca videos de YouTube por texto (sin API key de Google, via yt-dlp
 * `ytsearch:` del lado del backend) y deja elegir uno con un clic en vez de
 * tener que pegar la URL a mano. Busqueda solo al hacer clic en "Buscar"
 * (no mientras se escribe) para no generar una request por tecla.
 */
export function YoutubeSearchPanel({ onSelect }: YoutubeSearchPanelProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MediaPreview[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSearch() {
    if (!query.trim()) return
    setIsLoading(true)
    setError(null)
    try {
      const items = await searchYoutubeVideos(query.trim())
      setResults(items)
    } catch {
      setError('No se pudo buscar en este momento. Intenta de nuevo.')
    } finally {
      setIsLoading(false)
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    // No se usa un <form> propio: este panel vive dentro del <form> de la
    // pagina (crear proyecto), y HTML no permite formularios anidados -- un
    // <form> aca causaba que Enter/submit disparara el submit del formulario
    // externo en vez de solo la busqueda.
    if (event.key === 'Enter') {
      event.preventDefault()
      void handleSearch()
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Busca un video de YouTube…"
          className="flex-1"
        />
        <Button type="button" onClick={() => void handleSearch()} disabled={isLoading || !query.trim()}>
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Buscar
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {results && results.length === 0 && !error && (
        <p className="text-sm text-muted-foreground">Sin resultados para "{query}".</p>
      )}

      {results && results.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {results.map((item) => (
            <button
              key={item.source_url}
              type="button"
              onClick={() => onSelect(item.source_url)}
              className="flex flex-col overflow-hidden rounded-xl border border-border text-left transition-colors hover:border-primary"
            >
              <div className="aspect-video w-full bg-secondary">
                {item.thumbnail_url && (
                  <img
                    src={item.thumbnail_url}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                )}
              </div>
              <div className="flex flex-col gap-0.5 p-2">
                <p className="line-clamp-2 text-xs font-medium">{item.title}</p>
                {item.duration_seconds !== null && (
                  <p className="text-[11px] text-muted-foreground">
                    {formatClockTime(item.duration_seconds)}
                  </p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
