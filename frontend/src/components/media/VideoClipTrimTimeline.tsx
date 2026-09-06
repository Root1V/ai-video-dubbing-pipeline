import { useRef } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { formatClockTime } from '../../lib/format'

const MIN_CLIP_SPAN_SECONDS = 0.2

interface VideoClipTrimTimelineProps {
  duration: number
  start: number
  end: number
  onRangeChange: (start: number, end: number) => void
  disabled?: boolean
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

/** Franja horizontal para elegir el rango [start, end) de un clip de video a
 * usar en la linea de tiempo del micro-video (ver RM-36) -- mismo lugar y
 * criterio visual que AudioTrimPlayer (musica de fondo), pero sin forma de
 * onda: el audio del clip se descarta siempre (ver
 * GenerateMicroVideoUseCase, render_clip_video es mudo), asi que no hay
 * nada que graficar salvo la duracion.
 *
 * Arrastra los bordes para recortar (resize), o el cuerpo resaltado para
 * mover el rango entero conservando su duracion (drag) -- mismo
 * comportamiento que la region de wavesurfer que usa AudioTrimPlayer.
 * Mouse events puros (no Pointer Events/setPointerCapture): mismo criterio
 * que TextOverlayCanvas, evita un bug de larga data en Safari que rompe
 * pointermove/pointerup tras capturar el puntero. */
export function VideoClipTrimTimeline({
  duration,
  start,
  end,
  onRangeChange,
  disabled,
}: VideoClipTrimTimelineProps) {
  const trackRef = useRef<HTMLDivElement>(null)

  function fractionAt(clientX: number): number {
    const track = trackRef.current
    if (!track) return 0
    const rect = track.getBoundingClientRect()
    return clamp((clientX - rect.left) / rect.width, 0, 1)
  }

  function startDrag(onMove: (fraction: number) => void) {
    function handleMouseMove(event: MouseEvent) {
      onMove(fractionAt(event.clientX))
    }
    function handleMouseUp() {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  function handleStartHandleDown(event: ReactMouseEvent) {
    if (disabled) return
    event.preventDefault()
    event.stopPropagation()
    startDrag((fraction) => {
      onRangeChange(clamp(fraction * duration, 0, end - MIN_CLIP_SPAN_SECONDS), end)
    })
  }

  function handleEndHandleDown(event: ReactMouseEvent) {
    if (disabled) return
    event.preventDefault()
    event.stopPropagation()
    startDrag((fraction) => {
      onRangeChange(start, clamp(fraction * duration, start + MIN_CLIP_SPAN_SECONDS, duration))
    })
  }

  function handleRegionDown(event: ReactMouseEvent) {
    if (disabled) return
    event.preventDefault()
    const span = end - start
    // Offset (en segundos) entre donde cayo el click y el inicio del
    // rango -- se mantiene fijo durante todo el arrastre, para que el
    // punto bajo el cursor no "salte" al mover el rango entero.
    const clickOffsetSeconds = fractionAt(event.clientX) * duration - start
    startDrag((fraction) => {
      const newStart = clamp(fraction * duration - clickOffsetSeconds, 0, Math.max(0, duration - span))
      onRangeChange(newStart, newStart + span)
    })
  }

  const startPct = duration > 0 ? (start / duration) * 100 : 0
  const widthPct = duration > 0 ? ((end - start) / duration) * 100 : 100

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-secondary/30 p-4">
      <div className="flex items-center gap-3">
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{formatClockTime(start)}</span>
        <div ref={trackRef} className="relative h-14 flex-1 select-none rounded-lg bg-muted">
          <div
            onMouseDown={handleRegionDown}
            className="absolute inset-y-0 cursor-grab rounded-md bg-primary/20 active:cursor-grabbing"
            style={{ left: `${startPct}%`, width: `${widthPct}%` }}
          >
            <div
              onMouseDown={handleStartHandleDown}
              className="absolute inset-y-0 left-0 w-2.5 cursor-ew-resize rounded-l-md bg-primary"
              aria-label="Inicio del recorte"
            />
            <div
              onMouseDown={handleEndHandleDown}
              className="absolute inset-y-0 right-0 w-2.5 cursor-ew-resize rounded-r-md bg-primary"
              aria-label="Fin del recorte"
            />
          </div>
        </div>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{formatClockTime(end)}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        Arrastra los bordes para recortar el clip, o el centro para mover el fragmento elegido --
        dura {(end - start).toFixed(1)}s de {formatClockTime(duration)} en total.
      </p>
    </div>
  )
}
