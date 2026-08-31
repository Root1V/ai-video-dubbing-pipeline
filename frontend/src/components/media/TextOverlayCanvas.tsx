import type { PointerEvent as ReactPointerEvent } from 'react'
import { useRef } from 'react'
import type { TextOverlay } from '../../types/project'
import { cn } from '../../lib/cn'

interface TextOverlayCanvasProps {
  imageUrl: string
  overlays: TextOverlay[]
  selectedId: string | null
  onSelect: (id: string) => void
  onMove: (id: string, x: number, y: number) => void
}

/** Lienzo de edicion: la imagen de fondo (misma relacion de aspecto 9:16
 * que el video final) con cada TextOverlay encima, arrastrable a mano con
 * eventos de puntero nativos -- no hay libreria de drag-and-drop instalada
 * y no hace falta agregar una solo para mover unas pocas cajas libres (ver
 * RM-28 en docs/roadmap.md). `x`/`y` de cada overlay son fracciones 0-1 del
 * ancho/alto, asi que la posicion no depende del tamano en pantalla. */
export function TextOverlayCanvas({ imageUrl, overlays, selectedId, onSelect, onMove }: TextOverlayCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>, id: string) {
    event.preventDefault()
    onSelect(id)
    const container = containerRef.current
    if (!container) return
    const target = event.currentTarget
    target.setPointerCapture(event.pointerId)

    function handlePointerMove(moveEvent: PointerEvent) {
      if (!container) return
      const rect = container.getBoundingClientRect()
      const x = Math.min(1, Math.max(0, (moveEvent.clientX - rect.left) / rect.width))
      const y = Math.min(1, Math.max(0, (moveEvent.clientY - rect.top) / rect.height))
      onMove(id, x, y)
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
      className="relative mx-auto w-full max-w-xs select-none overflow-hidden rounded-2xl border border-border bg-secondary/30"
      style={{ aspectRatio: '9 / 16', containerType: 'inline-size' }}
    >
      <img src={imageUrl} alt="" className="h-full w-full object-cover" draggable={false} />
      {overlays.map((overlay) => (
        <div
          key={overlay.id}
          onPointerDown={(event) => handlePointerDown(event, overlay.id)}
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
    </div>
  )
}
