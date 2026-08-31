import { cn } from '../../../lib/cn'
import type { CaptionHighlightStyle } from '../../../types/project'

const HIGHLIGHT_STYLE_OPTIONS: { value: CaptionHighlightStyle; label: string; description: string }[] = [
  { value: 'background', label: 'Caja de fondo', description: 'Texto blanco sobre una caja de color' },
  { value: 'text_color', label: 'Color de texto', description: 'El texto toma el color, sin caja' },
]

interface SubtitlesPanelProps {
  highlightStyle: CaptionHighlightStyle
  onHighlightStyleChange: (style: CaptionHighlightStyle) => void
  captionBgColor: string
  onCaptionBgColorChange: (color: string) => void
}

export function SubtitlesPanel({
  highlightStyle,
  onHighlightStyleChange,
  captionBgColor,
  onCaptionBgColorChange,
}: SubtitlesPanelProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">Resaltado de los captions</span>
      <div className="flex flex-col gap-2">
        {HIGHLIGHT_STYLE_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onHighlightStyleChange(option.value)}
            className={cn(
              'flex flex-col items-start gap-0.5 rounded-xl border p-3 text-left transition-colors',
              highlightStyle === option.value
                ? 'border-primary bg-primary/5'
                : 'border-border hover:bg-secondary/50',
            )}
          >
            <span className="text-sm font-medium">{option.label}</span>
            <span className="text-xs text-muted-foreground">{option.description}</span>
          </button>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-3">
        <input
          id="caption-bg-color"
          type="color"
          value={captionBgColor}
          onChange={(e) => onCaptionBgColorChange(e.target.value)}
          className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-transparent p-1"
        />
        <label htmlFor="caption-bg-color" className="text-xs text-muted-foreground">
          {highlightStyle === 'text_color'
            ? 'Color del texto de los captions.'
            : 'Color de la caja de fondo -- el texto es siempre blanco.'}
        </label>
      </div>
    </div>
  )
}
