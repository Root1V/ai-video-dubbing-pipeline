import { cn } from '../../../lib/cn'
import type { CaptionHighlightStyle } from '../../../types/project'

const HIGHLIGHT_STYLE_OPTIONS: { value: CaptionHighlightStyle; label: string; description: string }[] = [
  { value: 'background', label: 'Caja de fondo', description: 'Texto sobre una caja de color' },
  { value: 'text_color', label: 'Color de texto', description: 'El texto toma el color, sin caja' },
  {
    value: 'karaoke',
    label: 'Karaoke (color por palabra)',
    description: 'La palabra que se está narrando cambia de color',
  },
  {
    value: 'karaoke_background',
    label: 'Karaoke (fondo por palabra)',
    description: 'La palabra que se está narrando resalta con un fondo de color, sin cambiar de color',
  },
]

// "background" y "karaoke_background" son los unicos dos estilos donde el
// texto y la caja/resaltado son colores INDEPENDIENTES (ver
// caption_text_color) -- en "text_color"/"karaoke" el unico color elegible
// ya es el del texto/la palabra, no hace falta un segundo picker.
const HAS_SEPARATE_TEXT_COLOR: Record<CaptionHighlightStyle, boolean> = {
  background: true,
  karaoke_background: true,
  text_color: false,
  karaoke: false,
}

interface SubtitlesPanelProps {
  highlightStyle: CaptionHighlightStyle
  onHighlightStyleChange: (style: CaptionHighlightStyle) => void
  captionBgColor: string
  onCaptionBgColorChange: (color: string) => void
  captionTextColor: string
  onCaptionTextColorChange: (color: string) => void
}

export function SubtitlesPanel({
  highlightStyle,
  onHighlightStyleChange,
  captionBgColor,
  onCaptionBgColorChange,
  captionTextColor,
  onCaptionTextColorChange,
}: SubtitlesPanelProps) {
  const hasTextColor = HAS_SEPARATE_TEXT_COLOR[highlightStyle]
  const bgColorLabel =
    highlightStyle === 'text_color'
      ? 'Color del texto'
      : highlightStyle === 'karaoke'
        ? 'Color de la palabra resaltada'
        : highlightStyle === 'karaoke_background'
          ? 'Color del fondo resaltado'
          : 'Color de la caja de fondo'

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
      <div className="mt-2 flex items-center gap-4">
        {hasTextColor && (
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Color del texto</span>
            <input
              type="color"
              value={captionTextColor}
              onChange={(e) => onCaptionTextColorChange(e.target.value)}
              className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-transparent p-1"
            />
          </div>
        )}
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">{bgColorLabel}</span>
          <input
            type="color"
            value={captionBgColor}
            onChange={(e) => onCaptionBgColorChange(e.target.value)}
            className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-transparent p-1"
          />
        </div>
      </div>
    </div>
  )
}
