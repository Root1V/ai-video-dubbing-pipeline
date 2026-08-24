import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import { Pause, Play } from 'lucide-react'
import { Button } from '../ui/Button'
import { formatClockTime } from '../../lib/format'

/** Reads a theme color as its raw "H S% L%" triplet (shadcn/Tailwind CSS
 * variable convention, see index.css) so the waveform matches the app's
 * palette instead of a hardcoded color that would clash if the theme
 * changes. Falls back to a sensible default if the variable isn't set
 * (e.g. during server-side rendering, which this app doesn't do, but keeps
 * the function safe to call unconditionally). */
function themeColor(cssVariable: string, fallback: string, alpha = 1): string {
  if (typeof window === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement).getPropertyValue(cssVariable).trim()
  if (!raw) return fallback
  return alpha < 1 ? `hsl(${raw} / ${alpha})` : `hsl(${raw})`
}

interface AudioWaveformPlayerProps {
  src: string
}

export function AudioWaveformPlayer({ src }: AudioWaveformPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const waveSurferRef = useRef<WaveSurfer | null>(null)
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

    ws.on('ready', () => {
      setIsReady(true)
      setDuration(ws.getDuration())
    })
    ws.on('play', () => setIsPlaying(true))
    ws.on('pause', () => setIsPlaying(false))
    ws.on('finish', () => setIsPlaying(false))
    ws.on('audioprocess', (time) => setCurrentTime(time))
    ws.on('seeking', (time) => setCurrentTime(time))

    return () => {
      ws.destroy()
      waveSurferRef.current = null
    }
  }, [src])

  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-secondary/30 p-4">
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
  )
}
