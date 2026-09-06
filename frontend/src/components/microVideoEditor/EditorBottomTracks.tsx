import { Music, Volume2 } from 'lucide-react'
import { AudioTrimPlayer } from '../media/AudioTrimPlayer'

interface EditorBottomTracksProps {
  hasMusic: boolean
  musicPreviewUrl: string | null
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

/** Franja inferior con la pista de música de fondo -- solo se muestra
 * mientras la herramienta "Música" está activa (ver NewMicroVideoProjectPage),
 * para no ocupar espacio permanente cuando el usuario está editando otra
 * cosa (imagen/video, texto, emoji, etc). El volumen de la narración vive
 * en NarrationPanel, no acá -- esta franja es exclusivamente de música. */
export function EditorBottomTracks({
  hasMusic,
  musicPreviewUrl,
  onRangeChange,
  musicKey,
  musicVolume,
  onMusicVolumeChange,
}: EditorBottomTracksProps) {
  return (
    <div className="flex shrink-0 gap-3 border-t border-border bg-card p-3">
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
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Music className="h-4 w-4" />
            </div>
            <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
              Elige una pista en el panel de la derecha.
            </span>
            <VolumeSlider value={musicVolume} onChange={onMusicVolumeChange} label="Volumen de la música de fondo" />
          </>
        )}
      </div>
    </div>
  )
}
