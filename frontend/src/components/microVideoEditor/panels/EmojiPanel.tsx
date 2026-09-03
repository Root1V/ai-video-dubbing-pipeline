import { Trash2 } from 'lucide-react'
import { EMOJI_PALETTE } from '../../../lib/emojiPalette'
import type { EmojiOverlay } from '../../../types/project'
import { Button } from '../../ui/Button'
import { Switch } from '../../ui/Switch'

interface EmojiPanelProps {
  hasImage: boolean
  overlays: EmojiOverlay[]
  selectedOverlayId: string | null
  onAddOverlay: (emojiId: string) => void
  onChangeOverlay: (overlay: EmojiOverlay) => void
  onRemoveOverlay: (id: string) => void
}

/** Panel de emojis del micro-video (ver RM-32): a diferencia del texto
 * (TextPanel), no hay texto libre -- se elige de un set curado de imágenes
 * bundleadas (el pipeline de texto del backend no puede renderizar emoji
 * Unicode en este sistema). Clic en un emoji de la grilla lo agrega
 * centrado en el lienzo; la posición se cambia arrastrando ahí, igual que
 * un TextOverlay. */
export function EmojiPanel({
  hasImage,
  overlays,
  selectedOverlayId,
  onAddOverlay,
  onChangeOverlay,
  onRemoveOverlay,
}: EmojiPanelProps) {
  if (!hasImage) {
    return <p className="text-sm text-muted-foreground">Sube una imagen primero para agregar emojis.</p>
  }

  const selected = overlays.find((o) => o.id === selectedOverlayId)

  return (
    <div className="flex flex-col gap-3">
      <span className="text-sm font-medium">Elegí un emoji para agregarlo</span>
      <div className="grid grid-cols-5 gap-1.5">
        {EMOJI_PALETTE.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onAddOverlay(item.id)}
            className="flex h-10 items-center justify-center rounded-lg border border-border text-xl transition-colors hover:bg-secondary/50"
            aria-label={`Agregar emoji ${item.id}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {selected ? (
        <div className="flex flex-col gap-3 rounded-xl border border-border p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">Emoji seleccionado</span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Quitar emoji"
              onClick={() => onRemoveOverlay(selected.id)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-muted-foreground">Tamaño</label>
            <input
              type="range"
              min={0.05}
              max={0.4}
              step={0.01}
              value={selected.size}
              onChange={(e) => onChangeOverlay({ ...selected, size: Number(e.target.value) })}
              className="accent-primary"
            />
          </div>

          <div className="flex items-center gap-2">
            <Switch
              checked={selected.fade}
              onCheckedChange={(checked) => onChangeOverlay({ ...selected, fade: checked })}
              id={`emoji-fade-${selected.id}`}
            />
            <label htmlFor={`emoji-fade-${selected.id}`} className="text-xs text-muted-foreground">
              Fade in/out
            </label>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {overlays.length === 0
            ? 'Todavía no agregaste ningún emoji. Hacé clic en uno de arriba.'
            : 'Hacé clic en un emoji del lienzo para editarlo.'}
        </p>
      )}
    </div>
  )
}
