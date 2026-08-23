import type { OutputMode, ProjectStage, ServiceType } from '../types/project'

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

function pluralize(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural
}

/** Picks the most useful metrics out of a stage's raw metadata (see
 * `pipeline_timings.json`'s `stages[]` entries) and formats them as a short,
 * human-readable summary -- e.g. "38 segmentos · 2 lotes" for translation.
 * Returns null when a stage has nothing notable beyond its duration. */
export function getStageSubtitle(stage: ProjectStage): string | null {
  const parts: string[] = []
  const num = (key: string): number | null => {
    const value = stage[key]
    return typeof value === 'number' ? value : null
  }

  switch (stage.name) {
    case 'transcription': {
      const segments = num('num_segments')
      if (segments !== null) parts.push(`${segments} ${pluralize(segments, 'segmento', 'segmentos')}`)
      break
    }
    case 'diarization': {
      const speakers = num('num_speakers')
      const turns = num('num_turns')
      if (speakers !== null) parts.push(`${speakers} ${pluralize(speakers, 'hablante', 'hablantes')}`)
      if (turns !== null) parts.push(`${turns} ${pluralize(turns, 'turno', 'turnos')}`)
      break
    }
    case 'speaker_profile_building': {
      const speakers = num('num_speakers')
      if (speakers !== null) parts.push(`${speakers} ${pluralize(speakers, 'perfil', 'perfiles')}`)
      break
    }
    case 'translation': {
      const segments = num('num_segments')
      const batches = num('num_batches')
      if (segments !== null) parts.push(`${segments} ${pluralize(segments, 'segmento', 'segmentos')}`)
      if (batches !== null) parts.push(`${batches} ${pluralize(batches, 'lote', 'lotes')}`)
      break
    }
    case 'tts_synthesis': {
      const groups = num('num_groups')
      const jobs = num('num_jobs')
      const reduction = num('grouping_reduction_pct')
      if (groups !== null) parts.push(`${groups} ${pluralize(groups, 'grupo', 'grupos')}`)
      else if (jobs !== null) parts.push(`${jobs} ${pluralize(jobs, 'trabajo', 'trabajos')}`)
      if (reduction !== null) parts.push(`${reduction.toFixed(1)}% menos llamadas`)
      break
    }
    default:
      break
  }

  if (stage.ran_concurrently) parts.push('en paralelo')

  return parts.length > 0 ? parts.join(' · ') : null
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
