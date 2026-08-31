import { Mic, Music, Volume2 } from 'lucide-react'
import { AudioTrimPlayer } from '../media/AudioTrimPlayer'
import { Button } from '../ui/Button'

interface EditorBottomTracksProps {
  narrationText: string
  onNarrationClick: () => void
  narrationVolume: number
  onNarrationVolumeChange: (volume: number) => void
  hasMusic: boolean
  musicPreviewUrl: string | null
  onMusicClick: () => void
  onRangeChange: (start: number, end: number) => void
  musicKey: string | null
  musicVolume: number
  onMusicVolumeChange: (volume: number) => void
}

/** Slider vertical (una rotacion CSS sobre un <input type="range"> normal --
 * mas confiable entre navegadores que "orient=vertical" o "writing-mode"). */
function VolumeSlider({
  value,
  onChange,
  label,
}: {
  value: number
  onChange: (value: number) => void
  label: string
}) {
  return (
    <div className="flex shrink-0 flex-col items-center gap-1.5">
      <Volume2 className="h-3.5 w-3.5 text-muted-foreground" />
      <div className="flex h-20 w-5 items-center justify-center">
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-1.5 w-20 -rotate-90 cursor-pointer accent-primary"
          aria-label={label}
          aria-orientation="vertical"
        />
      </div>
    </div>
  )
}

/** Franja inferior con las "pistas" del video, tipo timeline de un editor
 * profesional -- SIEMPRE dos paneles (narracion y musica), cada uno
 * opcional en si mismo pero visibles con la misma estructura para que
 * quede claro que son dos pistas independientes. Narracion no tiene un
 * archivo de audio real todavia (la sintesis pasa en el backend recien al
 * generar), asi que se muestra un preview del texto en vez de inventar una
 * forma de onda. Cada pista tiene su propio control de volumen vertical,
 * que tambien afecta la reproduccion real del preview (no solo el archivo
 * final). */
export function EditorBottomTracks({
  narrationText,
  onNarrationClick,
  narrationVolume,
  onNarrationVolumeChange,
  hasMusic,
  musicPreviewUrl,
  onMusicClick,
  onRangeChange,
  musicKey,
  musicVolume,
  onMusicVolumeChange,
}: EditorBottomTracksProps) {
  return (
    <div className="flex shrink-0 gap-3 border-t border-border bg-card p-3">
      <div className="flex flex-1 items-center gap-3 rounded-xl border border-border p-2.5">
        <button
          type="button"
          onClick={onNarrationClick}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left transition-colors hover:bg-secondary/50"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Mic className="h-4 w-4" />
          </div>
          <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
            {narrationText.trim() ? narrationText.trim().slice(0, 100) : 'Sin texto a narrar todavía…'}
          </span>
        </button>
        <VolumeSlider value={narrationVolume} onChange={onNarrationVolumeChange} label="Volumen de la narración" />
      </div>

      <div className="flex flex-1 items-center gap-3 rounded-xl border border-border p-2.5">
        {hasMusic && musicPreviewUrl ? (
          <>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Music className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <AudioTrimPlayer
                key={musicKey}
                src={musicPreviewUrl}
                onRangeChange={onRangeChange}
                volume={musicVolume}
              />
            </div>
            <VolumeSlider value={musicVolume} onChange={onMusicVolumeChange} label="Volumen de la música de fondo" />
          </>
        ) : (
          <>
            <Button type="button" variant="ghost" className="min-w-0 flex-1 justify-start gap-3 px-0" onClick={onMusicClick}>
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Music className="h-4 w-4" />
              </div>
              <span className="truncate text-sm text-muted-foreground">Sin música -- elegir pista</span>
            </Button>
            <VolumeSlider value={musicVolume} onChange={onMusicVolumeChange} label="Volumen de la música de fondo" />
          </>
        )}
      </div>
    </div>
  )
}
