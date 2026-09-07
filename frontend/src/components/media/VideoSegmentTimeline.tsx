import { useEffect, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Redo2, Scissors, Trash2, Undo2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { cn } from '../../lib/cn'
import { formatClockTime } from '../../lib/format'

const MIN_SPAN_SECONDS = 0.2
// Dos tramos que quedan a esta distancia o menos se consideran "unidos" (ver
// mergeAdjacentRanges) -- evita que arrastrar uno hasta tocar al otro deje
// un hueco microscopico por errores de redondeo del arrastre.
const MERGE_EPSILON_SECONDS = 0.05

interface VideoSegmentTimelineProps {
  duration: number
  /** Tramo(s) conservados del clip, en orden cronologico y sin solaparse
   * (ver RM-40) -- lo que queda afuera de esta lista se descarta. */
  keepRanges: [number, number][]
  onChange: (ranges: [number, number][]) => void
  /** Doble clic en la franja (ver mejora pedida tras probar RM-40): saltar
   * el preview a ese punto exacto para inspeccionarlo. */
  onSeek: (time: number) => void
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

/** Fusiona tramos que quedaron tocandose o superpuestos (ver mejora pedida
 * tras probar RM-40: arrastrar un tramo en modo "mano" hasta juntarlo con
 * su vecino "cierra" el hueco que habia quedado entre medio) -- sin esto,
 * dos tramos exactamente contiguos quedarian separados innecesariamente en
 * el modelo de datos (y del lado del backend, como dos sub-segmentos a
 * concatenar en vez de uno solo). */
function mergeAdjacentRanges(ranges: [number, number][]): [number, number][] {
  const sorted = [...ranges].sort((a, b) => a[0] - b[0])
  const merged: [number, number][] = []
  for (const [start, end] of sorted) {
    const last = merged[merged.length - 1]
    if (last && start <= last[1] + MERGE_EPSILON_SECONDS) {
      last[1] = Math.max(last[1], end)
    } else {
      merged.push([start, end])
    }
  }
  return merged
}

/** Franja horizontal para elegir QUE tramos de un clip de video conservar
 * en la linea de tiempo del micro-video (ver RM-40) -- reemplaza el
 * recorte de un unico rango de RM-36: ahora se pueden quitar varios
 * tramos sueltos (uno cerca del inicio, otro del medio, otro del final) y
 * quedarse solo con el resto, en su orden cronologico original. Sin forma
 * de onda: el audio del clip se descarta siempre (ver
 * GenerateMicroVideoUseCase, render_clip_video es mudo).
 *
 * Interacciones (mejoradas tras probar la v1 de RM-40):
 * - Modo ESTANDAR (por defecto, cursor de mano): arrastrar DENTRO de un
 *   tramo lo MUEVE a lo largo del clip (que parte de la fuente usa),
 *   sin poder cruzar a sus vecinos -- arrastrarlo hasta tocar el tramo de
 *   al lado "une" las dos partes que un corte hubiera separado.
 * - Modo CORTE (activado con el boton de tijera, cursor de cruz): arrastrar
 *   DENTRO de un tramo marca una seleccion pendiente (contorno punteado),
 *   moviendo el preview EN VIVO al punto hasta el cual se va extendiendo
 *   (para ver que contenido se va a perder, no elegirlo a ciegas) -- el
 *   boton de tacho (o las teclas Delete/Backspace) la convierte en un
 *   corte real, partiendo el tramo, y el modo vuelve solo al estandar.
 * - Arrastrar el borde IZQUIERDO del primer tramo o el DERECHO del
 *   ultimo (en cualquier modo): resize del rango exterior (equivalente al
 *   recorte de inicio/fin de RM-36).
 * - Doble clic en cualquier punto de la franja: salta el preview a ese
 *   punto exacto (pausado, para inspeccionar el frame) -- funciona sobre
 *   un tramo conservado o sobre un hueco ya eliminado por igual.
 * - Deshacer/Rehacer (botones + Cmd+Z / Cmd+Shift+Z, o Ctrl en no-Mac):
 *   un historial LOCAL a este componente -- se reinicia solo porque la
 *   pagina lo remonta con `key={activeMediaIndex}` al cambiar de item, no
 *   persiste entre recargas.
 *
 * En esta v1 los bordes INTERIORES (entre un tramo conservado y un hueco)
 * no son arrastrables por separado -- se ajustan moviendo el tramo entero
 * en modo estandar. Mouse events puros (no Pointer Events/
 * setPointerCapture): mismo criterio que TextOverlayCanvas, evita un bug
 * de larga data en Safari que rompe pointermove/pointerup tras capturar
 * el puntero. */
export function VideoSegmentTimeline({
  duration,
  keepRanges,
  onChange,
  onSeek,
  disabled,
}: VideoSegmentTimelineProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [cutMode, setCutMode] = useState(false)
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
  // borde/tramo, o al confirmar un borrado), nunca en cada paso intermedio
  // de un drag, para que deshacer un arrastre lo deshaga entero de una.
  function pushHistory(previous: [number, number][]) {
    setPast((p) => [...p, previous])
    setFuture([])
  }

  // `onChange` (que dispara un setState del componente PADRE) se llama
  // aca afuera de cualquier actualizador funcional de setState -- llamarlo
  // DENTRO de uno (como se hacia antes) actualiza un componente distinto
  // mientras React todavia esta resolviendo el render de este, lo cual
  // React marca como invalido (advertencia real, confirmada en la
  // practica). undo/redo se disparan desde un evento discreto (click o
  // atajo de teclado), no en cada paso de un drag, asi que leer `past`/
  // `future` directo del closure (sin forma funcional) es seguro aca.
  function undo() {
    if (past.length === 0) return
    const previous = past[past.length - 1]
    setPast(past.slice(0, -1))
    setFuture([keepRanges, ...future])
    onChange(previous)
  }

  function redo() {
    if (future.length === 0) return
    const next = future[0]
    setFuture(future.slice(1))
    setPast([...past, keepRanges])
    onChange(next)
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
    // Una vez cortado, vuelve sola al modo estandar (mejora pedida tras
    // probar RM-40) -- cortar es una accion puntual, no un modo en el que
    // quedarse trabajado.
    setCutMode(false)
  }

  function toggleCutMode() {
    if (disabled) return
    setPendingSelection(null)
    setCutMode((prev) => !prev)
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

  // Modo CORTE: arrastrar dentro de un tramo marca una seleccion pendiente
  // a eliminar (ver commitDelete). Ademas, mueve el preview al punto HASTA
  // el cual se esta extendiendo la seleccion (mejora pedida tras probar
  // RM-40: sin esto, se elegia el tramo a borrar "a ciegas", sin ver que
  // contenido se iba a perder). Se throttlea a ~20 saltos/seg -- onSeek
  // dispara un setState en la pagina que re-renderiza el lienzo entero,
  // y mousemove nativo llega mucho mas seguido que eso durante un arrastre
  // rapido.
  function handleRangeBodySelect(event: ReactMouseEvent, range: [number, number]) {
    if (disabled) return
    event.preventDefault()
    const [rangeStart, rangeEnd] = range
    const anchor = clamp(fractionAt(event.clientX) * duration, rangeStart, rangeEnd)
    setPendingSelection([anchor, anchor])
    onSeek(anchor)
    let lastSeekAt = 0
    startDrag((fraction) => {
      const current = clamp(fraction * duration, rangeStart, rangeEnd)
      setPendingSelection([Math.min(anchor, current), Math.max(anchor, current)])
      const now = performance.now()
      if (now - lastSeekAt > 50) {
        lastSeekAt = now
        onSeek(current)
      }
    })
  }

  // Modo ESTANDAR (default): arrastrar dentro de un tramo lo MUEVE entero
  // a lo largo del clip -- clamp para que no pueda cruzar a sus vecinos, y
  // fusiona con el vecino si termina tocandolo (ver mergeAdjacentRanges),
  // que es lo que "une" dos partes separadas por un corte anterior.
  function handleRangeBodyMove(event: ReactMouseEvent, index: number) {
    if (disabled) return
    event.preventDefault()
    const [start, end] = keepRanges[index]
    const span = end - start
    const prevEnd = index > 0 ? keepRanges[index - 1][1] : 0
    const nextStart = index < keepRanges.length - 1 ? keepRanges[index + 1][0] : duration
    const clickOffsetSeconds = fractionAt(event.clientX) * duration - start
    pushHistory(keepRanges)
    startDrag((fraction) => {
      const desiredStart = fraction * duration - clickOffsetSeconds
      const newStart = clamp(desiredStart, prevEnd, nextStart - span)
      const moved = keepRanges.map((r, i): [number, number] => (i === index ? [newStart, newStart + span] : r))
      onChange(mergeAdjacentRanges(moved))
    })
  }

  function handleTrackDoubleClick(event: ReactMouseEvent) {
    if (disabled) return
    onSeek(fractionAt(event.clientX) * duration)
  }

  const totalKept = keepRanges.reduce((sum, [start, end]) => sum + (end - start), 0)

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-secondary/30 p-4">
      <div className="flex items-center gap-3">
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{formatClockTime(0)}</span>
        <div
          ref={trackRef}
          onDoubleClick={handleTrackDoubleClick}
          className="relative h-14 flex-1 select-none rounded-lg bg-muted"
        >
          {keepRanges.map(([start, end], index) => {
            const isFirst = index === 0
            const isLast = index === keepRanges.length - 1
            return (
              <div
                key={`${start}-${end}`}
                onMouseDown={(event) =>
                  cutMode ? handleRangeBodySelect(event, [start, end]) : handleRangeBodyMove(event, index)
                }
                className={cn(
                  'absolute inset-y-0 rounded-md bg-primary/20',
                  cutMode ? 'cursor-crosshair' : 'cursor-grab active:cursor-grabbing',
                )}
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
          {cutMode
            ? 'Arrastra dentro de un tramo para elegir que eliminar.'
            : 'Arrastra un tramo para moverlo (y unir los que quedaron separados), o los bordes para recortar. Doble clic para saltar a un punto.'}{' '}
          Dura {totalKept.toFixed(1)}s de {formatClockTime(duration)} en total.
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
            onClick={toggleCutMode}
            disabled={disabled}
            aria-label={cutMode ? 'Desactivar herramienta de corte' : 'Activar herramienta de corte'}
            aria-pressed={cutMode}
            className={cn('h-8 w-8', cutMode && 'bg-primary/10 text-primary')}
          >
            <Scissors className="h-4 w-4" />
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
