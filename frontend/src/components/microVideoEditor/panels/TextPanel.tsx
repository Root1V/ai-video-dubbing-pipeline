import { Plus } from 'lucide-react'
import { Button } from '../../ui/Button'
import { TextOverlayPanel } from '../../media/TextOverlayPanel'
import type { TextOverlay } from '../../../types/project'

interface TextPanelProps {
  hasImage: boolean
  overlays: TextOverlay[]
  selectedOverlayId: string | null
  onAddOverlay: () => void
  onChangeOverlay: (overlay: TextOverlay) => void
  onRemoveOverlay: (id: string) => void
}

export function TextPanel({
  hasImage,
  overlays,
  selectedOverlayId,
  onAddOverlay,
  onChangeOverlay,
  onRemoveOverlay,
}: TextPanelProps) {
  if (!hasImage) {
    return <p className="text-sm text-muted-foreground">Sube una imagen primero para agregar texto.</p>
  }

  const selected = overlays.find((o) => o.id === selectedOverlayId)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Texto sobre la imagen</span>
        <Button type="button" variant="outline" size="sm" onClick={onAddOverlay}>
          <Plus className="h-4 w-4" />
          Agregar texto
        </Button>
      </div>
      {selected ? (
        <TextOverlayPanel
          overlay={selected}
          onChange={onChangeOverlay}
          onRemove={() => onRemoveOverlay(selected.id)}
        />
      ) : (
        <p className="text-sm text-muted-foreground">
          {overlays.length === 0
            ? 'Todavía no agregaste texto. Usa "Agregar texto" o hacé clic en uno del lienzo.'
            : 'Hacé clic en un texto del lienzo para editarlo.'}
        </p>
      )}
    </div>
  )
}
