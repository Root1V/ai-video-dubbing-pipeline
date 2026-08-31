import { Trash2 } from 'lucide-react'
import type { TextOverlay } from '../../types/project'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Switch } from '../ui/Switch'
import { Button } from '../ui/Button'

const FONT_OPTIONS = ['Arial', 'Georgia', 'Impact', 'Courier New', 'Comic Sans MS']

interface TextOverlayPanelProps {
  overlay: TextOverlay
  onChange: (overlay: TextOverlay) => void
  onRemove: () => void
}

/** Controles del overlay seleccionado en TextOverlayCanvas: texto, negrita,
 * tipografia, tamano, color y fade in/out (ver RM-28). La posicion se
 * cambia arrastrando en el canvas, no aca. */
export function TextOverlayPanel({ overlay, onChange, onRemove }: TextOverlayPanelProps) {
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

      <div className="flex items-center gap-3">
        <input
          type="color"
          value={overlay.color}
          onChange={(e) => onChange({ ...overlay, color: e.target.value })}
          className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-transparent p-1"
        />
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
