import type { PointerEvent as ReactPointerEvent } from 'react'
import { useRef } from 'react'
import type { CaptionHighlightStyle, TextOverlay } from '../../types/project'
import { cn } from '../../lib/cn'

export interface CaptionPreview {
  x: number
  y: number
  text: string
  bgColor: string
  highlightStyle: CaptionHighlightStyle
}

interface TextOverlayCanvasProps {
  imageUrl: string
  overlays: TextOverlay[]
  selectedId: string | null
  onSelect: (id: string) => void
  onMove: (id: string, x: number, y: number) => void
  /** Preview arrastrable de donde van a aparecer los captions de la
   * narracion -- mismo mecanismo de drag que un TextOverlay, pero es un
   * singleton (no forma parte de la lista de overlays). undefined = no
   * mostrar nada (p.ej. sin narracion todavia). */
  captionPreview?: CaptionPreview
  onCaptionMove?: (x: number, y: number) => void
}

/** Lienzo de edicion: la imagen de fondo (misma relacion de aspecto 9:16
 * que el video final) con cada TextOverlay encima, arrastrable a mano con
 * eventos de puntero nativos -- no hay libreria de drag-and-drop instalada
 * y no hace falta agregar una solo para mover unas pocas cajas libres (ver
 * RM-28 en docs/roadmap.md). `x`/`y` de cada overlay son fracciones 0-1 del
 * ancho/alto, asi que la posicion no depende del tamano en pantalla. */
export function TextOverlayCanvas({
  imageUrl,
  overlays,
  selectedId,
  onSelect,
  onMove,
  captionPreview,
  onCaptionMove,
}: TextOverlayCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  function handlePointerDown(
    event: ReactPointerEvent<HTMLDivElement>,
    onDrag: (x: number, y: number) => void,
  ) {
    event.preventDefault()
    const container = containerRef.current
    if (!container) return
    const target = event.currentTarget
    target.setPointerCapture(event.pointerId)

    function handlePointerMove(moveEvent: PointerEvent) {
      if (!container) return
      const rect = container.getBoundingClientRect()
      const x = Math.min(1, Math.max(0, (moveEvent.clientX - rect.left) / rect.width))
      const y = Math.min(1, Math.max(0, (moveEvent.clientY - rect.top) / rect.height))
      onDrag(x, y)
    }

    function handlePointerUp() {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
  }

  return (
    <div
      ref={containerRef}
      className="relative mx-auto h-full max-h-full max-w-full select-none overflow-hidden rounded-2xl border border-border bg-secondary/30 shadow-lg"
      style={{ aspectRatio: '9 / 16', containerType: 'inline-size' }}
    >
      <img src={imageUrl} alt="" className="h-full w-full object-cover" draggable={false} />
      {overlays.map((overlay) => (
        <div
          key={overlay.id}
          onPointerDown={(event) => {
            onSelect(overlay.id)
            handlePointerDown(event, (x, y) => onMove(overlay.id, x, y))
          }}
          className={cn(
            'absolute max-w-[90%] -translate-x-1/2 -translate-y-1/2 cursor-move whitespace-pre-wrap px-1 text-center',
            overlay.id === selectedId && 'outline outline-2 outline-dashed outline-primary',
          )}
          style={{
            left: `${overlay.x * 100}%`,
            top: `${overlay.y * 100}%`,
            fontFamily: overlay.font_family,
            fontWeight: overlay.bold ? 'bold' : 'normal',
            color: overlay.color,
            // El tamano de fuente en el video final esta en px sobre un
            // ancho de 1080 -- se escala al ancho real del canvas en pantalla.
            fontSize: `${(overlay.font_size / 1080) * 100}cqw`,
            textShadow: '0 0 3px rgba(0,0,0,0.8)',
          }}
        >
          {overlay.text || 'Texto'}
        </div>
      ))}
      {captionPreview && (
        <div
          onPointerDown={(event) => handlePointerDown(event, (x, y) => onCaptionMove?.(x, y))}
          className="absolute max-w-[85%] -translate-x-1/2 -translate-y-1/2 cursor-move whitespace-pre-wrap rounded px-2 py-1 text-center text-sm font-semibold"
          style={{
            left: `${captionPreview.x * 100}%`,
            top: `${captionPreview.y * 100}%`,
            ...(captionPreview.highlightStyle === 'text_color'
              ? { color: captionPreview.bgColor, textShadow: '0 0 3px rgba(0,0,0,0.9)' }
              : { color: '#FFFFFF', backgroundColor: captionPreview.bgColor }),
          }}
        >
          {captionPreview.text}
        </div>
      )}
    </div>
  )
}
