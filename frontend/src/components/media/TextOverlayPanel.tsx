import { Trash2 } from 'lucide-react'
import type { TextOverlay, TextStyle } from '../../types/project'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Switch } from '../ui/Switch'
import { Button } from '../ui/Button'
import { cn } from '../../lib/cn'

// Arial/Impact quedan como opciones "seguras" (siempre disponibles en
// cualquier sistema); el resto son tipografias bundleadas por el backend
// (ver RM-33, assets/fonts/) -- probadas a mano, no dependen de que esten
// instaladas en la maquina.
const FONT_OPTIONS = ['Arial', 'Impact', 'Bebas Neue', 'Montserrat', 'Poppins', 'Righteous', 'Pacifico', 'Dancing Script']

const TEXT_STYLE_OPTIONS: { value: TextStyle; label: string }[] = [
  { value: 'flat', label: 'Normal' },
  { value: 'hard_shadow', label: 'Sombra dura' },
  { value: 'thick_outline', label: 'Contorno grueso' },
  { value: 'long_shadow', label: 'Sombra larga' },
  { value: 'hollow', label: 'Solo contorno' },
  { value: 'neon_glow', label: 'Neón' },
  { value: 'colored_outline', label: 'Contorno de color' },
  { value: 'gradient', label: 'Degradado' },
]

// Label del segundo color picker ("accent_color") -- su significado
// depende del estilo activo (ver RM-33). Un estilo sin entrada aca no
// muestra ese picker (no lo usa).
const ACCENT_COLOR_LABELS: Partial<Record<TextStyle, string>> = {
  gradient: 'Color final',
  neon_glow: 'Color del brillo',
  colored_outline: 'Color del contorno',
}

interface TextOverlayPanelProps {
  overlay: TextOverlay
  onChange: (overlay: TextOverlay) => void
  onRemove: () => void
}

/** Controles del overlay seleccionado en TextOverlayCanvas: texto, negrita,
 * tipografia, tamano, color y fade in/out (ver RM-28). La posicion se
 * cambia arrastrando en el canvas, no aca. */
export function TextOverlayPanel({ overlay, onChange, onRemove }: TextOverlayPanelProps) {
  const accentLabel = ACCENT_COLOR_LABELS[overlay.text_style]
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">Texto seleccionado</span>
        <Button type="button" variant="ghost" size="icon" aria-label="Quitar texto" onClick={onRemove}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      <Input
        value={overlay.text}
        onChange={(e) => onChange({ ...overlay, text: e.target.value })}
        placeholder="Escribe el texto…"
      />

      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-muted-foreground">Tipografía</label>
          <Select
            value={overlay.font_family}
            onChange={(e) => onChange({ ...overlay, font_family: e.target.value })}
          >
            {FONT_OPTIONS.map((font) => (
              <option key={font} value={font}>
                {font}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-muted-foreground">Tamaño</label>
          <Input
            type="number"
            min={16}
            max={200}
            value={overlay.font_size}
            onChange={(e) => onChange({ ...overlay, font_size: Number(e.target.value) || overlay.font_size })}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-muted-foreground">Estilo</label>
        <div className="flex flex-wrap gap-1.5">
          {TEXT_STYLE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange({ ...overlay, text_style: option.value })}
              className={cn(
                'rounded-full border px-3 py-1 text-xs transition-colors',
                overlay.text_style === option.value
                  ? 'border-primary bg-primary/5 font-medium'
                  : 'border-border hover:bg-secondary/50',
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex flex-col gap-1">
          {accentLabel && <span className="text-xs text-muted-foreground">Color inicial</span>}
          <input
            type="color"
            value={overlay.color}
            onChange={(e) => onChange({ ...overlay, color: e.target.value })}
            className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-transparent p-1"
          />
        </div>
        {accentLabel && (
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">{accentLabel}</span>
            <input
              type="color"
              value={overlay.accent_color}
              onChange={(e) => onChange({ ...overlay, accent_color: e.target.value })}
              className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-transparent p-1"
            />
          </div>
        )}
        <div className="flex items-center gap-2">
          <Switch
            checked={overlay.bold}
            onCheckedChange={(checked) => onChange({ ...overlay, bold: checked })}
            id={`overlay-bold-${overlay.id}`}
          />
          <label htmlFor={`overlay-bold-${overlay.id}`} className="text-xs text-muted-foreground">
            Negrita
          </label>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            checked={overlay.fade}
            onCheckedChange={(checked) => onChange({ ...overlay, fade: checked })}
            id={`overlay-fade-${overlay.id}`}
          />
          <label htmlFor={`overlay-fade-${overlay.id}`} className="text-xs text-muted-foreground">
            Fade in/out
          </label>
        </div>
      </div>
    </div>
  )
}
