import { Mic, Music } from 'lucide-react'
import { AudioTrimPlayer } from '../media/AudioTrimPlayer'
import { Button } from '../ui/Button'

interface EditorBottomTracksProps {
  narrationText: string
  onNarrationClick: () => void
  hasMusic: boolean
  musicPreviewUrl: string | null
  onMusicClick: () => void
  onRangeChange: (start: number, end: number) => void
  musicKey: string | null
}

/** Franja inferior con las "pistas" del video, tipo timeline de un editor
 * profesional -- Narracion no tiene un archivo de audio real todavia (la
 * sintesis pasa en el backend recien al generar), asi que se muestra un
 * preview del texto en vez de inventar una forma de onda o una duracion
 * estimada que no se puede calcular de forma confiable en el cliente. */
export function EditorBottomTracks({
  narrationText,
  onNarrationClick,
  hasMusic,
  musicPreviewUrl,
  onMusicClick,
  onRangeChange,
  musicKey,
}: EditorBottomTracksProps) {
  return (
    <div className="flex shrink-0 flex-col gap-2 border-t border-border bg-card p-3">
      <button
        type="button"
        onClick={onNarrationClick}
        className="flex items-center gap-3 rounded-xl border border-border p-2.5 text-left transition-colors hover:bg-secondary/50"
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Mic className="h-4 w-4" />
        </div>
        <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
          {narrationText.trim() ? narrationText.trim().slice(0, 100) : 'Sin texto a narrar todavía…'}
        </span>
      </button>

      {hasMusic && musicPreviewUrl ? (
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Music className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <AudioTrimPlayer key={musicKey} src={musicPreviewUrl} onRangeChange={onRangeChange} />
          </div>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-fit"
          onClick={onMusicClick}
        >
          <Music className="h-4 w-4" />
          Sin música -- elegir pista
        </Button>
      )}
    </div>
  )
}
