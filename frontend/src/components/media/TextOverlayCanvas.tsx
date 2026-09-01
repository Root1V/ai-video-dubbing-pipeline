import type { PointerEvent as ReactPointerEvent } from 'react'
import { useRef } from 'react'
import type { CaptionHighlightStyle, FilterPreset, ImageAdjustment, TextOverlay } from '../../types/project'
import { cn } from '../../lib/cn'

// Aproximacion visual (no un match exacto de pixeles) de los presets de
// color de RM-31 -- el filtro real se aplica en ffmpeg al generar el video.
// 'dramatic' no tiene equivalente nativo de vinieta en CSS `filter`, se
// aproxima por separado con un overlay radial (ver DRAMATIC_VIGNETTE_STYLE).
const CSS_FILTER_BY_PRESET: Record<FilterPreset, string | undefined> = {
  none: undefined,
  sepia: 'sepia(0.8)',
  bw: 'grayscale(1)',
  cool: 'hue-rotate(180deg) saturate(1.1)',
  warm: 'sepia(0.3) saturate(1.3) hue-rotate(-10deg)',
  dramatic: 'contrast(1.15) saturate(1.2)',
}

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
  /** Encuadre (pan/zoom) de la imagen de fondo actualmente activa (ver
   * RM-30) -- undefined = sin ajuste (recorte centrado, comportamiento
   * previo). `onImagePan` habilita arrastrar la imagen para reposicionarla. */
  imageAdjustment?: ImageAdjustment
  onImagePan?: (offsetX: number, offsetY: number) => void
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
  imageAdjustment,
  onImagePan,
}: TextOverlayCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  function handlePointerDown(
    event: ReactPointerEvent<HTMLElement>,
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

  // A diferencia de handlePointerDown (mapea la posicion ABSOLUTA del
  // puntero, natural para "donde soltaste el texto"), reposicionar una
  // imagen se siente como arrastrar una foto: el contenido debe seguir al
  // cursor. Se acumula el DELTA de movimiento y se resta del offset actual
  // -- arrastrar hacia la derecha revela mas del lado izquierdo de la
  // imagen, igual que un editor de recorte de foto estandar.
  function handleImagePointerDown(event: ReactPointerEvent<HTMLImageElement>) {
    const pan = onImagePan
    if (!pan || !imageAdjustment) return
    event.preventDefault()
    const container = containerRef.current
    if (!container) return
    const target = event.currentTarget
    target.setPointerCapture(event.pointerId)
    let lastX = event.clientX
    let lastY = event.clientY
    let offsetX = imageAdjustment.offset_x
    let offsetY = imageAdjustment.offset_y

    function handlePointerMove(moveEvent: PointerEvent) {
      if (!container) return
      const rect = container.getBoundingClientRect()
      offsetX = Math.min(1, Math.max(0, offsetX - (moveEvent.clientX - lastX) / rect.width))
      offsetY = Math.min(1, Math.max(0, offsetY - (moveEvent.clientY - lastY) / rect.height))
      lastX = moveEvent.clientX
      lastY = moveEvent.clientY
      pan?.(offsetX, offsetY)
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
      <img
        src={imageUrl}
        alt=""
        className={cn('h-full w-full object-cover', onImagePan && 'cursor-move')}
        draggable={false}
        onPointerDown={onImagePan ? handleImagePointerDown : undefined}
        style={
          imageAdjustment
            ? {
                objectPosition: `${imageAdjustment.offset_x * 100}% ${imageAdjustment.offset_y * 100}%`,
                transform: `scale(${imageAdjustment.zoom})`,
                filter: CSS_FILTER_BY_PRESET[imageAdjustment.filter_preset],
              }
            : undefined
        }
      />
      {imageAdjustment?.filter_preset === 'dramatic' && (
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.55) 100%)' }}
        />
      )}
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
