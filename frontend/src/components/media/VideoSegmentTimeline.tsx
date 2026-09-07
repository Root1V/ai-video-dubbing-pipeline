import { useEffect, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Redo2, Trash2, Undo2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { cn } from '../../lib/cn'
import { formatClockTime } from '../../lib/format'

const MIN_SPAN_SECONDS = 0.2

interface VideoSegmentTimelineProps {
  duration: number
  /** Tramo(s) conservados del clip, en orden cronologico y sin solaparse
   * (ver RM-40) -- lo que queda afuera de esta lista se descarta. */
  keepRanges: [number, number][]
  onChange: (ranges: [number, number][]) => void
  disabled?: boolean
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

/** Resta `cut` de cada rango de `ranges` -- parte un rango en dos si el
 * corte cae en el medio, lo acorta si cae en un borde, o lo elimina del
 * todo si el corte lo cubre por completo. */
function subtractRange(ranges: [number, number][], cut: [number, number]): [number, number][] {
  const [cutStart, cutEnd] = cut
  const result: [number, number][] = []
  for (const [start, end] of ranges) {
    if (cutEnd <= start || cutStart >= end) {
      result.push([start, end])
      continue
    }
    if (cutStart > start) result.push([start, cutStart])
    if (cutEnd < end) result.push([cutEnd, end])
  }
  return result
}

/** Franja horizontal para elegir QUE tramos de un clip de video conservar
 * en la linea de tiempo del micro-video (ver RM-40) -- reemplaza el
 * recorte de un unico rango de RM-36: ahora se pueden quitar varios
 * tramos sueltos (uno cerca del inicio, otro del medio, otro del final) y
 * quedarse solo con el resto, en su orden cronologico original. Sin forma
 * de onda: el audio del clip se descarta siempre (ver
 * GenerateMicroVideoUseCase, render_clip_video es mudo).
 *
 * Interacciones:
 * - Arrastrar el borde IZQUIERDO del primer tramo o el DERECHO del
 *   ultimo: resize del rango exterior (equivalente al recorte de
 *   inicio/fin de RM-36).
 * - Arrastrar DENTRO de un tramo conservado (no sobre un borde): marca una
 *   seleccion pendiente (contorno punteado) -- el boton de tacho (o las
 *   teclas Delete/Backspace) la convierte en un corte real, partiendo el
 *   tramo. Arrastrar sobre un hueco ya eliminado no hace nada.
 * - Deshacer/Rehacer (botones + Cmd+Z / Cmd+Shift+Z, o Ctrl en no-Mac):
 *   un historial LOCAL a este componente -- se reinicia solo porque la
 *   pagina lo remonta con `key={activeMediaIndex}` al cambiar de item, no
 *   persiste entre recargas.
 *
 * En esta v1 los bordes INTERIORES (entre un tramo conservado y un hueco)
 * no son arrastrables -- para ajustar un corte ya hecho, se deshace y se
 * vuelve a seleccionar. Mouse events puros (no Pointer Events/
 * setPointerCapture): mismo criterio que TextOverlayCanvas, evita un bug
 * de larga data en Safari que rompe pointermove/pointerup tras capturar
 * el puntero. */
export function VideoSegmentTimeline({
  duration,
  keepRanges,
  onChange,
  disabled,
}: VideoSegmentTimelineProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [pendingSelection, setPendingSelection] = useState<[number, number] | null>(null)
  const [past, setPast] = useState<[number, number][][]>([])
  const [future, setFuture] = useState<[number, number][][]>([])

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

  // Un unico punto de entrada al historial -- SIEMPRE se llama con el
  // estado ANTES del cambio (una vez por gesto: al empezar un arrastre de
  // borde, o al confirmar un borrado), nunca en cada paso intermedio de un
  // drag, para que deshacer un arrastre lo deshaga entero de una.
  function pushHistory(previous: [number, number][]) {
    setPast((p) => [...p, previous])
    setFuture([])
  }

  function undo() {
    setPast((p) => {
      if (p.length === 0) return p
      const previous = p[p.length - 1]
      setFuture((f) => [keepRanges, ...f])
      onChange(previous)
      return p.slice(0, -1)
    })
  }

  function redo() {
    setFuture((f) => {
      if (f.length === 0) return f
      const next = f[0]
      setPast((p) => [...p, keepRanges])
      onChange(next)
      return f.slice(1)
    })
  }

  function commitDelete() {
    if (!pendingSelection || disabled) return
    const [start, end] = pendingSelection
    if (end - start < MIN_SPAN_SECONDS) {
      setPendingSelection(null)
      return
    }
    const next = subtractRange(keepRanges, [start, end])
    if (next.length === 0) {
      // No se puede borrar TODO lo que queda -- un item necesita conservar
      // al menos un tramo.
      setPendingSelection(null)
      return
    }
    pushHistory(keepRanges)
    onChange(next)
    setPendingSelection(null)
  }

  // Cmd+Z / Cmd+Shift+Z (Ctrl en no-Mac) deshace/rehace; Delete/Backspace
  // confirma una seleccion pendiente -- ignorado si el foco esta en un
  // campo de texto, para no pisar el undo nativo del navegador en otra
  // parte del editor.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const active = document.activeElement
      if (active instanceof HTMLElement && ['INPUT', 'TEXTAREA'].includes(active.tagName)) return
      const meta = event.metaKey || event.ctrlKey
      if (meta && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        if (event.shiftKey) redo()
        else undo()
      } else if ((event.key === 'Delete' || event.key === 'Backspace') && pendingSelection) {
        event.preventDefault()
        commitDelete()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- undo/redo/commitDelete cierran sobre keepRanges/past/future/pendingSelection, listados aca
  }, [keepRanges, past, future, pendingSelection])

  function handleStartHandleDown(event: ReactMouseEvent) {
    if (disabled || keepRanges.length === 0) return
    event.preventDefault()
    event.stopPropagation()
    pushHistory(keepRanges)
    const [, firstEnd] = keepRanges[0]
    const rest = keepRanges.slice(1)
    startDrag((fraction) => {
      const newStart = clamp(fraction * duration, 0, firstEnd - MIN_SPAN_SECONDS)
      onChange([[newStart, firstEnd], ...rest])
    })
  }

  function handleEndHandleDown(event: ReactMouseEvent) {
    if (disabled || keepRanges.length === 0) return
    event.preventDefault()
    event.stopPropagation()
    pushHistory(keepRanges)
    const lastIndex = keepRanges.length - 1
    const [lastStart] = keepRanges[lastIndex]
    const head = keepRanges.slice(0, lastIndex)
    startDrag((fraction) => {
      const newEnd = clamp(fraction * duration, lastStart + MIN_SPAN_SECONDS, duration)
      onChange([...head, [lastStart, newEnd]])
    })
  }

  function handleRangeBodyDown(event: ReactMouseEvent, range: [number, number]) {
    if (disabled) return
    event.preventDefault()
    const [rangeStart, rangeEnd] = range
    const anchor = clamp(fractionAt(event.clientX) * duration, rangeStart, rangeEnd)
    setPendingSelection([anchor, anchor])
    startDrag((fraction) => {
      const current = clamp(fraction * duration, rangeStart, rangeEnd)
      setPendingSelection([Math.min(anchor, current), Math.max(anchor, current)])
    })
  }

  const totalKept = keepRanges.reduce((sum, [start, end]) => sum + (end - start), 0)

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-secondary/30 p-4">
      <div className="flex items-center gap-3">
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{formatClockTime(0)}</span>
        <div ref={trackRef} className="relative h-14 flex-1 select-none rounded-lg bg-muted">
          {keepRanges.map(([start, end], index) => {
            const isFirst = index === 0
            const isLast = index === keepRanges.length - 1
            return (
              <div
                key={`${start}-${end}`}
                onMouseDown={(event) => handleRangeBodyDown(event, [start, end])}
                className="absolute inset-y-0 cursor-crosshair rounded-md bg-primary/20"
                style={{ left: `${(start / duration) * 100}%`, width: `${((end - start) / duration) * 100}%` }}
              >
                {isFirst && (
                  <div
                    onMouseDown={handleStartHandleDown}
                    className="absolute inset-y-0 left-0 w-2.5 cursor-ew-resize rounded-l-md bg-primary"
                    aria-label="Inicio del primer tramo conservado"
                  />
                )}
                {isLast && (
                  <div
                    onMouseDown={handleEndHandleDown}
                    className="absolute inset-y-0 right-0 w-2.5 cursor-ew-resize rounded-r-md bg-primary"
                    aria-label="Fin del último tramo conservado"
                  />
                )}
              </div>
            )
          })}
          {pendingSelection && (
            <div
              className="pointer-events-none absolute inset-y-0 rounded-md border-2 border-dashed border-destructive bg-destructive/10"
              style={{
                left: `${(pendingSelection[0] / duration) * 100}%`,
                width: `${((pendingSelection[1] - pendingSelection[0]) / duration) * 100}%`,
              }}
            />
          )}
        </div>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{formatClockTime(duration)}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Arrastra los bordes para recortar, o dentro de un tramo para seleccionar y eliminarlo --
          dura {totalKept.toFixed(1)}s de {formatClockTime(duration)} en total.
        </p>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={undo}
            disabled={disabled || past.length === 0}
            aria-label="Deshacer"
            className="h-8 w-8"
          >
            <Undo2 className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={redo}
            disabled={disabled || future.length === 0}
            aria-label="Rehacer"
            className="h-8 w-8"
          >
            <Redo2 className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={commitDelete}
            disabled={disabled || !pendingSelection}
            aria-label="Eliminar el tramo seleccionado"
            className={cn('h-8 w-8', pendingSelection && 'text-destructive')}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
