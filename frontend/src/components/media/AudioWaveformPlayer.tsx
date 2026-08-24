import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import { Pause, Play } from 'lucide-react'
import { Button } from '../ui/Button'
import { formatClockTime } from '../../lib/format'
import { themeColor } from '../../lib/theme-color'
import { computeAmplitudeEnvelope } from '../../lib/audio-peaks'
import { LiveWaveformVisualizer, BAR_COUNT } from './LiveWaveformVisualizer'

interface AudioWaveformPlayerProps {
  src: string
}

export function AudioWaveformPlayer({ src }: AudioWaveformPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const waveSurferRef = useRef<WaveSurfer | null>(null)
  const [mediaElement, setMediaElement] = useState<HTMLMediaElement | null>(null)
  const [peaks, setPeaks] = useState<number[] | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isReady, setIsReady] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    if (!containerRef.current) return

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: themeColor('--muted-foreground', '#a1a1aa', 0.35),
      progressColor: themeColor('--primary', '#635bff'),
      cursorColor: 'transparent',
      barWidth: 2,
      barGap: 2,
      barRadius: 2,
      height: 56,
      normalize: true,
      url: src,
    })
    waveSurferRef.current = ws
    setMediaElement(ws.getMediaElement())

    ws.on('ready', () => {
      setIsReady(true)
      setDuration(ws.getDuration())
      const decoded = ws.getDecodedData()
      if (decoded) setPeaks(computeAmplitudeEnvelope(decoded, BAR_COUNT))
    })
    ws.on('play', () => setIsPlaying(true))
    ws.on('pause', () => setIsPlaying(false))
    ws.on('finish', () => setIsPlaying(false))
    ws.on('audioprocess', (time) => setCurrentTime(time))
    ws.on('seeking', (time) => setCurrentTime(time))

    return () => {
      ws.destroy()
      waveSurferRef.current = null
      setMediaElement(null)
      setPeaks(null)
    }
  }, [src])

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-secondary/30 p-4">
      {/* Ecualizador reactivo: se mueve con el audio real mientras suena,
          independiente de la forma de onda estatica de abajo (que sigue
          mostrando la pista completa y sirve de barra de progreso/seek). */}
      <LiveWaveformVisualizer mediaElement={mediaElement} peaks={peaks} />
      <div className="flex items-center gap-3">
        <Button
          type="button"
          size="icon"
          onClick={() => waveSurferRef.current?.playPause()}
          disabled={!isReady}
          aria-label={isPlaying ? 'Pausar' : 'Reproducir'}
          className="shrink-0 rounded-full"
        >
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </Button>
        <div ref={containerRef} className="min-w-0 flex-1" />
        <span className="shrink-0 font-mono text-xs text-muted-foreground">
          {formatClockTime(currentTime)} / {formatClockTime(duration)}
        </span>
      </div>
    </div>
  )
}
