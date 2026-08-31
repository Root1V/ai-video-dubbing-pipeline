import { Textarea } from '../../ui/Textarea'
import { Select } from '../../ui/Select'
import { cn } from '../../../lib/cn'
import { LANGUAGE_NAMES } from '../../../lib/labels'

const LANGUAGE_OPTIONS = Object.entries(LANGUAGE_NAMES).map(([code, name]) => ({
  value: code,
  label: name.charAt(0).toUpperCase() + name.slice(1),
}))

// Duraciones estándar de video corto por plataforma: 15s (viral en Reels),
// 30s (Reels/TikTok), 60s (TikTok/Shorts), 90s (máximo recomendado en
// Facebook Reels). "Automático" (null) mantiene el comportamiento previo:
// el video dura lo que tarda la narración.
const DURATION_OPTIONS: { value: number | null; label: string }[] = [
  { value: null, label: 'Automático' },
  { value: 15, label: '15s' },
  { value: 30, label: '30s' },
  { value: 60, label: '60s' },
  { value: 90, label: '90s' },
]

interface NarrationPanelProps {
  text: string
  onTextChange: (text: string) => void
  targetLang: string
  onTargetLangChange: (lang: string) => void
  targetDuration: number | null
  onTargetDurationChange: (duration: number | null) => void
}

export function NarrationPanel({
  text,
  onTextChange,
  targetLang,
  onTargetLangChange,
  targetDuration,
  onTargetDurationChange,
}: NarrationPanelProps) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="text" className="text-sm font-medium">
          Texto a narrar
        </label>
        <Textarea
          id="text"
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          placeholder="Escribe aquí el texto que se va a narrar sobre la imagen…"
          rows={8}
        />
        <p className="text-xs text-muted-foreground">
          Tip: envolvé una palabra o frase entre <code>**así**</code> para que aparezca en{' '}
          <strong>negrita</strong> en los captions (no se narra en voz alta).
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="target-lang" className="text-sm font-medium">
          Idioma de la narración
        </label>
        <Select id="target-lang" value={targetLang} onChange={(e) => onTargetLangChange(e.target.value)}>
          {LANGUAGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Duración del video</span>
        <div className="grid grid-cols-3 gap-2">
          {DURATION_OPTIONS.map((option) => (
            <button
              key={option.label}
              type="button"
              onClick={() => onTargetDurationChange(option.value)}
              className={cn(
                'rounded-xl border p-2 text-center text-sm font-medium transition-colors',
                targetDuration === option.value
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:bg-secondary/50',
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Automático: el video dura lo que tarda la narración. Con una duración fija, la narración se
          acelera si es más larga o se mantiene la imagen si es más corta.
        </p>
      </div>
    </div>
  )
}
