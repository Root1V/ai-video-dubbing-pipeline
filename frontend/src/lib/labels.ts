import type { OutputMode, ServiceType } from '../types/project'

export const SERVICE_TYPE_LABELS: Record<ServiceType, string> = {
  dubbing: 'Doblaje',
  subtitles: 'Subtítulos',
  transcription: 'Transcripción',
}

export const OUTPUT_MODE_LABELS: Record<OutputMode, string> = {
  subtitles_only: 'Solo subtítulos',
  burn_subtitles: 'Subtítulos incrustados',
  soft_subtitles: 'Subtítulos seleccionables',
  dubbed: 'Doblado',
}
