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

/** Human-readable Spanish names for the pipeline's internal stage
 * identifiers (see `utils/timing.py` / `application/use_cases/translate_video.py`). */
export const STAGE_LABELS: Record<string, string> = {
  audio_extraction: 'Extracción de audio',
  transcription: 'Transcripción',
  diarization: 'Detección de hablantes',
  speaker_profile_building: 'Perfiles de hablantes',
  translation: 'Traducción',
  subtitles_writing: 'Generación de subtítulos',
  tts_synthesis: 'Síntesis de voz',
  audio_mixing_and_muxing: 'Mezcla de audio',
  rendering_dubbed: 'Renderizado del video doblado',
  rendering_soft_subtitles: 'Adjuntando subtítulos',
  rendering_burn_subtitles: 'Incrustando subtítulos',
}

/** Falls back to a humanized version of the raw stage name (e.g.
 * "some_new_stage" -> "Some new stage") for any stage not in the map above
 * yet, so a future pipeline stage never renders as a raw snake_case string. */
export function getStageLabel(name: string): string {
  if (STAGE_LABELS[name]) return STAGE_LABELS[name]
  const humanized = name.replace(/_/g, ' ')
  return humanized.charAt(0).toUpperCase() + humanized.slice(1)
}

const RENDERING_STAGE_BY_MODE: Partial<Record<OutputMode, string>> = {
  dubbed: 'rendering_dubbed',
  soft_subtitles: 'rendering_soft_subtitles',
  burn_subtitles: 'rendering_burn_subtitles',
  // subtitles_only never renders a video -- no stage.
}

/** Predicts the full ordered list of stages this project WILL go through,
 * based on its mode/diarize config, mirroring
 * `application/use_cases/translate_video.py`'s real stage sequence. The
 * backend only ever reports stages that already started/finished (see
 * `pipeline_timings.json`), so this is what lets the UI show the whole plan
 * upfront and progressively fill it in, instead of stages only appearing
 * one by one as they happen. */
export function getExpectedStageNames(outputMode: OutputMode, diarize: boolean): string[] {
  const names: string[] = ['audio_extraction', 'transcription']
  if (diarize) {
    names.push('diarization', 'speaker_profile_building')
  }
  names.push('translation', 'subtitles_writing')
  if (outputMode === 'dubbed') {
    names.push('tts_synthesis', 'audio_mixing_and_muxing')
  }
  const renderingStage = RENDERING_STAGE_BY_MODE[outputMode]
  if (renderingStage) names.push(renderingStage)
  return names
}
