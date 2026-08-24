import { useEffect, useRef } from 'react'
import { themeColor } from '../../lib/theme-color'

export const BAR_COUNT = 48
const IDLE_BAR_LEVEL = 0.06
const ATTACK_RATE = 0.55
const DECAY_RATE = 0.1
/** Cuantas barras justo detras de la cabeza de reproduccion siguen
 * reaccionando en vivo (en vez de quedar fijas en su pico) -- suficientes
 * para que se vea una "ola" moviendose, no solo una aguja suelta. */
const LIVE_TRAIL_BARS = 6

interface AudioGraph {
  context: AudioContext
  analyser: AnalyserNode
  source: MediaElementAudioSourceNode
  data: Uint8Array<ArrayBuffer>
}

function drawRoundedBar(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
) {
  const radius = Math.min(width / 2, height / 2)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + width, y, x + width, y + height, radius)
  ctx.arcTo(x + width, y + height, x, y + height, radius)
  ctx.arcTo(x, y + height, x, y, radius)
  ctx.arcTo(x, y, x + width, y, radius)
  ctx.closePath()
  ctx.fill()
}

interface LiveWaveformVisualizerProps {
  mediaElement: HTMLMediaElement | null
  /** Normalized (0-1) RMS amplitude per bar, one entry per BAR_COUNT segment
   * across the full track -- see lib/audio-peaks.ts. Bars reveal themselves
   * at this real height as playback reaches their time segment, so the
   * shape matches the static waveform below instead of an arbitrary live
   * frequency reading. Null while the track is still decoding. */
  peaks: number[] | null
}

/**
 * Live playback-position visualizer meant to sit alongside the static
 * waveform a player already draws (see AudioWaveformPlayer) -- that one
 * keeps showing the overall shape/progress of the track; this one "reveals"
 * that same shape bar by bar as playback reaches each time segment (using
 * `peaks`, precomputed once from the decoded audio), with the bar AT the
 * current playhead blended with REAL live loudness from a Web Audio
 * AnalyserNode (time-domain RMS) so it visibly pulses with the actual
 * audio instead of just jumping to a fixed height.
 *
 * Bars are smoothed frame-to-frame with a fast attack / slow decay curve
 * (professional audio-meter convention: jump up quickly, fall back slowly)
 * rather than snapping straight to their target, which reads as jittery.
 * Seeking backward correctly "unreveals" bars ahead of the new position.
 *
 * Like any canvas animation, requestAnimationFrame pauses while the tab is
 * hidden/unfocused -- that's standard browser behavior (audio itself keeps
 * playing; only the visual redraw pauses), not something this component
 * needs to work around.
 */
export function LiveWaveformVisualizer({ mediaElement, peaks }: LiveWaveformVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const audioGraphRef = useRef<AudioGraph | null>(null)
  const levelsRef = useRef<number[]>(new Array(BAR_COUNT).fill(0))
  const peaksRef = useRef<number[] | null>(peaks)
  peaksRef.current = peaks

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !mediaElement) return
    const ctx2d = canvas.getContext('2d')
    if (!ctx2d) return

    function ensureAudioGraph(): AudioGraph | null {
      if (audioGraphRef.current) return audioGraphRef.current
      try {
        const AudioContextCtor =
          window.AudioContext ??
          (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        if (!AudioContextCtor || !mediaElement) return null
        const context = new AudioContextCtor()
        const analyser = context.createAnalyser()
        analyser.fftSize = 128
        const source = context.createMediaElementSource(mediaElement)
        source.connect(analyser)
        analyser.connect(context.destination)
        const graph: AudioGraph = {
          context,
          analyser,
          source,
          data: new Uint8Array(new ArrayBuffer(analyser.fftSize)),
        }
        audioGraphRef.current = graph
        return graph
      } catch {
        // Un <audio> ya conectado a un AudioContext (p.ej. React StrictMode
        // re-ejecutando este efecto) no se puede volver a envolver -- se
        // degrada en silencio a la linea base quieta, sin romper la
        // reproduccion ni la forma de onda estatica de al lado.
        return null
      }
    }

    /** RMS del dominio del tiempo (0-1): una sola lectura de "que tan fuerte
     * suena ahora mismo", en la misma escala (RMS normalizado) que los picos
     * precalculados de `peaks`, para que la barra actual no salte a una
     * escala visualmente distinta de sus vecinas ya reveladas. */
    function readLiveLevel(graph: AudioGraph): number {
      graph.analyser.getByteTimeDomainData(graph.data)
      let sumSquares = 0
      for (let i = 0; i < graph.data.length; i++) {
        const v = (graph.data[i] - 128) / 128
        sumSquares += v * v
      }
      return Math.sqrt(sumSquares / graph.data.length)
    }

    function resizeCanvas() {
      const rect = canvas!.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas!.width = Math.max(1, Math.round(rect.width * dpr))
      canvas!.height = Math.max(1, Math.round(rect.height * dpr))
      ctx2d!.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resizeCanvas()
    const resizeObserver = new ResizeObserver(resizeCanvas)
    resizeObserver.observe(canvas)

    let frameId: number

    function draw() {
      const rect = canvas!.getBoundingClientRect()
      const width = rect.width
      const height = rect.height
      ctx2d!.clearRect(0, 0, width, height)

      const playing = mediaElement !== null && !mediaElement.paused && !mediaElement.ended
      const graph = playing ? ensureAudioGraph() : audioGraphRef.current
      if (graph?.context.state === 'suspended') graph.context.resume().catch(() => {})
      const liveLevel = playing && graph ? readLiveLevel(graph) : 0

      const duration = mediaElement?.duration || 0
      const currentTime = mediaElement?.currentTime || 0
      const progressBars = duration > 0 ? (currentTime / duration) * BAR_COUNT : 0
      const currentBarIndex = Math.floor(progressBars)
      const barsPeaks = peaksRef.current

      const gradient = ctx2d!.createLinearGradient(0, height, 0, 0)
      gradient.addColorStop(0, themeColor('--primary', '#635bff'))
      gradient.addColorStop(1, themeColor('--accent', '#8b5cf6'))
      ctx2d!.fillStyle = gradient
      if (playing) {
        ctx2d!.shadowColor = themeColor('--primary', '#635bff', 0.45)
        ctx2d!.shadowBlur = 6
      } else {
        ctx2d!.shadowBlur = 0
      }

      const barWidth = width / BAR_COUNT
      const gap = barWidth * 0.3
      const levels = levelsRef.current

      for (let i = 0; i < BAR_COUNT; i++) {
        const basePeak = barsPeaks ? barsPeaks[i] : 0
        let target = IDLE_BAR_LEVEL
        const distanceBehindPlayhead = currentBarIndex - i
        if (playing && distanceBehindPlayhead >= 0 && distanceBehindPlayhead < LIVE_TRAIL_BARS) {
          // Ventana "viva" justo detras de la cabeza de reproduccion: se
          // mezcla con el nivel EN VIVO del audio real (que sube Y baja de
          // verdad, no solo un piso) para dar sensacion de onda -- pesando
          // cada vez mas su propio pico real cuanto mas atras haya quedado,
          // para que se vaya "asentando" en vez de cortar en seco.
          const liveWeight = 1 - distanceBehindPlayhead / LIVE_TRAIL_BARS
          target = basePeak * (1 - liveWeight) + liveLevel * liveWeight
        } else if (i < currentBarIndex) {
          // Ya asentado, fuera de la ventana viva: se queda en su altura
          // real (misma forma que la onda estatica de abajo).
          target = Math.max(IDLE_BAR_LEVEL, basePeak)
        }
        const prev = levels[i]
        const rate = target > prev ? ATTACK_RATE : DECAY_RATE
        levels[i] = prev + (target - prev) * rate

        const barHeight = Math.max(2, levels[i] * height)
        const x = i * barWidth + gap / 2
        const y = height - barHeight
        drawRoundedBar(ctx2d!, x, y, barWidth - gap, barHeight)
      }

      frameId = requestAnimationFrame(draw)
    }

    frameId = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(frameId)
      resizeObserver.disconnect()
    }
  }, [mediaElement])

  // El grafo de Web Audio (AudioContext + nodos) vive mientras el elemento de
  // audio exista -- se libera solo al desmontar o cambiar de pista, no en
  // cada re-render, para no perder la conexion (createMediaElementSource
  // solo puede llamarse una vez por elemento).
  useEffect(() => {
    return () => {
      const graph = audioGraphRef.current
      if (!graph) return
      graph.source.disconnect()
      graph.analyser.disconnect()
      graph.context.close().catch(() => {})
      audioGraphRef.current = null
    }
  }, [mediaElement])

  return <canvas ref={canvasRef} className="block h-16 w-full" aria-hidden="true" />
}
