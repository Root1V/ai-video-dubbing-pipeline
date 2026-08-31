import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import { Pause, Play } from 'lucide-react'
import { Button } from '../ui/Button'
import { formatClockTime } from '../../lib/format'
import { themeColor } from '../../lib/theme-color'

interface AudioTrimPlayerProps {
  src: string
  onRangeChange: (start: number, end: number) => void
  /** Volumen lineal 0-1 -- se aplica a la reproducción real del preview, no
   * solo al archivo final (ver mejora pedida tras probar RM-28). */
  volume: number
}

/** Igual que AudioWaveformPlayer, pero agrega el plugin de Regions de
 * wavesurfer.js (ya incluido en el paquete instalado, sin dependencia
 * nueva) para elegir a mano el fragmento de la pista a usar como fondo
 * (ver RM-28) -- arrastra los bordes de la región resaltada. */
export function AudioTrimPlayer({ src, onRangeChange, volume }: AudioTrimPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const waveSurferRef = useRef<WaveSurfer | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isReady, setIsReady] = useState(false)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    if (!containerRef.current) return

    const regions = RegionsPlugin.create()
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
      plugins: [regions],
    })
    waveSurferRef.current = ws
    ws.setVolume(volume)

    ws.on('ready', () => {
      setIsReady(true)
      const total = ws.getDuration()
      setDuration(total)
      regions.addRegion({
        start: 0,
        end: total,
        color: 'rgba(99, 91, 255, 0.15)',
        drag: true,
        resize: true,
      })
      onRangeChange(0, total)
    })
    ws.on('play', () => setIsPlaying(true))
    ws.on('pause', () => setIsPlaying(false))
    ws.on('finish', () => setIsPlaying(false))
    regions.on('region-updated', (region) => onRangeChange(region.start, region.end))

    return () => {
      ws.destroy()
      waveSurferRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onRangeChange solo reenvia a setState, estable en la practica; volume se sincroniza en el effect de abajo
  }, [src])

  useEffect(() => {
    waveSurferRef.current?.setVolume(volume)
  }, [volume])

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-secondary/30 p-4">
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
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{formatClockTime(duration)}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        Arrastra los bordes de la región resaltada para elegir el fragmento a usar.
      </p>
    </div>
  )
}
