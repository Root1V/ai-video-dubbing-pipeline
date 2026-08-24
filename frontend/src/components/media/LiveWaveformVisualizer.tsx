import { useEffect, useRef } from 'react'
import { themeColor } from '../../lib/theme-color'

const BAR_COUNT = 48
const IDLE_BAR_LEVEL = 0.06
const ATTACK_RATE = 0.55
const DECAY_RATE = 0.1

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
}

/**
 * Live, audio-reactive bar visualizer meant to sit alongside the static
 * waveform a player already draws (see AudioWaveformPlayer) -- that one
 * keeps showing the overall shape/progress of the track; this one reads
 * REAL frequency data from the actual playing audio (Web Audio API
 * AnalyserNode) and animates continuously via requestAnimationFrame, so the
 * player feels alive while something is actually playing instead of a
 * static image with a moving playhead.
 *
 * Bars are smoothed frame-to-frame with a fast attack / slow decay curve
 * (professional audio-meter convention: jump up quickly, fall back slowly)
 * rather than snapping straight to the raw FFT bins, which reads as
 * jittery. Falls back to a flat idle baseline (no crash, no console noise)
 * if the browser refuses to wire up an AudioContext for this element.
 *
 * Like any canvas animation, requestAnimationFrame pauses while the tab is
 * hidden/unfocused -- that's standard browser behavior (audio itself keeps
 * playing; only the visual redraw pauses), not something this component
 * needs to work around.
 */
export function LiveWaveformVisualizer({ mediaElement }: LiveWaveformVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const audioGraphRef = useRef<AudioGraph | null>(null)
  const levelsRef = useRef<number[]>(new Array(BAR_COUNT).fill(0))

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
        analyser.smoothingTimeConstant = 0.75
        const source = context.createMediaElementSource(mediaElement)
        source.connect(analyser)
        analyser.connect(context.destination)
        const graph: AudioGraph = {
          context,
          analyser,
          source,
          data: new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount)),
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
      if (playing && graph) {
        if (graph.context.state === 'suspended') graph.context.resume().catch(() => {})
        graph.analyser.getByteFrequencyData(graph.data)
      }

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
      const usableBins = graph ? Math.floor(graph.data.length * 0.8) : 0

      for (let i = 0; i < BAR_COUNT; i++) {
        let target = IDLE_BAR_LEVEL
        if (playing && graph) {
          const binIndex = 2 + Math.floor((i / BAR_COUNT) * usableBins)
          target = Math.max(IDLE_BAR_LEVEL, (graph.data[binIndex] ?? 0) / 255)
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
