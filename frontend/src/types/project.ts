export type ServiceType = 'dubbing' | 'subtitles' | 'transcription' | 'tts' | 'micro_video'

export type OutputMode =
  | 'subtitles_only'
  | 'burn_subtitles'
  | 'soft_subtitles'
  | 'dubbed'

export type ProjectStatus =
  | 'queued'
  | 'downloading'
  | 'running'
  | 'completed'
  | 'failed'

export interface Project {
  id: string
  user_id: string
  name: string
  service_type: ServiceType
  source_type: string
  source_url: string | null
  output_mode: OutputMode
  config: Record<string, unknown>
  status: ProjectStatus
  celery_task_id: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  /** Not a DB column -- filled in from pipeline_timings.json (see
   * status_reader.py) so the projects list doesn't need a second /status
   * call per row. Null until the run has actually written that file. */
  total_seconds: number | null
  run_id: string | null
}

export interface ProjectListResponse {
  items: Project[]
  total: number
  page: number
  page_size: number
}

export interface ProjectListParams {
  status?: ProjectStatus
  service_type?: ServiceType
  page?: number
  page_size?: number
}

/**
 * Shape of an individual pipeline stage as surfaced by `pipeline_timings.json`.
 * The backend stub for M1 will not populate this yet, so consumers must treat
 * every field here as possibly absent and render defensively.
 */
export interface ProjectStage {
  name: string
  status?: string
  seconds?: number
  [key: string]: unknown
}

/** Matches `PipelineTimings.as_dict()["current_stage"]` — present only while a
 * stage is in flight, absent (null) when idle/completed. It is an object
 * (`{name, started_at}`), not a bare stage name string. */
export interface CurrentStage {
  name: string
  started_at?: string
  [key: string]: unknown
}

/** Matches an entry in `PipelineTimings.as_dict()["warnings"]` (added via
 * `timings.add_warning(**w)`). Always has a `source`, plus arbitrary extra
 * fields that vary by warning type (e.g. `segment_index`, `overflow_seconds`
 * for `audio_mixing.overflow_after_compression`) — not a plain string. */
export interface PipelineWarning {
  source: string
  [key: string]: unknown
}

export interface ProjectStatusResponse {
  db_status: ProjectStatus
  run_id: string | null
  completed: boolean | null
  current_stage: CurrentStage | null
  stages: ProjectStage[] | Record<string, unknown> | null
  total_seconds: number | null
  realtime_factor: number | null
  warnings: PipelineWarning[] | null
}

export type DownloadArtifact =
  | 'video'
  | 'srt_source'
  | 'srt_target'
  | 'transcript_srt'
  | 'transcript_text'
  | 'summary_text'
  | 'speech_audio'

export interface GlossaryEntry {
  term: string
  translation: string
}

export interface CreateDubbingProjectInput {
  name: string
  /** Exactamente uno de `file`/`source_url` -- ver components/media/MediaSourceInput.tsx. */
  file?: File
  source_url?: string
  context_prompt?: string
  tone?: string
  glossary?: Record<string, string>
  source_lang?: string
  target_lang?: string
  diarize?: boolean
  min_speakers?: number
  max_speakers?: number
}

export interface CreateSubtitlesProjectInput {
  name: string
  /** Exactamente uno de `file`/`source_url` -- ver components/media/MediaSourceInput.tsx. */
  file?: File
  source_url?: string
  /** subtitles_only ".srt" / burn_subtitles (incrustados) / soft_subtitles
   * (pista seleccionable) -- "dubbed" no aplica a este servicio. */
  output_mode: Exclude<OutputMode, 'dubbed'>
  context_prompt?: string
  tone?: string
  glossary?: Record<string, string>
  source_lang?: string
  target_lang?: string
}

export interface CreateTranscriptionProjectInput {
  name: string
  /** Exactamente uno de `file`/`source_url` -- ver components/media/MediaSourceInput.tsx. */
  file?: File
  source_url?: string
  /** Vacio = detectar automaticamente (el backend lo trata como None, ver
   * `Transcriber.transcribe(language_hint=None)`). */
  source_lang?: string
  /** Ademas de la transcripcion completa, genera un resumen con los
   * highlights via LLM (ver TranscribeMediaUseCase). */
  include_summary?: boolean
}

export type TtsVoiceOption = 'public_female' | 'public_male' | 'own'

export interface CreateTtsProjectInput {
  name: string
  text: string
  /** Idioma en el que se sintetiza el audio. */
  target_lang?: string
  /** "public_female" (voz de locutora, por defecto) / "public_male" (voz de
   * locutor) / "own" (usa `voiceFile` como voz de referencia). */
  voice_option: TtsVoiceOption
  voiceFile?: File
}

export interface CreateMicroVideoProjectInput {
  name: string
  text: string
  /** Al menos una imagen -- si hay varias, el video las recorre en orden,
   * cada una con su propio efecto Ken Burns (ver RM-29). */
  imageFiles: File[]
  /** Idioma en el que se narra el texto. */
  target_lang?: string
  /** "public_female" (voz de locutora, por defecto) / "public_male" (voz de
   * locutor) / "own" (usa `voiceFile` como voz de referencia). */
  voice_option: TtsVoiceOption
  voiceFile?: File
  /** undefined/null = el video dura lo que tarda la narracion. Si se fija,
   * el audio se acelera para encajar (mas largo) o se mantiene la imagen el
   * tiempo restante (mas corto). */
  target_duration_seconds?: number
  /** Color del resaltado de los captions, "#RRGGBB" -- ver caption_highlight_style. */
  caption_bg_color?: string
  /** "background" (default) = caja de fondo de ese color detras del texto
   * blanco. "text_color" = el texto queda de ese color, sin caja. */
  caption_highlight_style?: CaptionHighlightStyle
  /** Id de una pista de música (ver MUSIC_OPTIONS en NewMicroVideoProjectPage),
   * o undefined = sin música de fondo. */
  background_music?: string
  /** Rango [start, end) dentro de la pista a usar como fuente del loop de
   * fondo (ver RM-28) -- undefined = la pista completa. */
  background_music_start?: number
  background_music_end?: number
  /** Volumen lineal (no dB) de la música de fondo al mezclarla, 0-1. */
  background_music_volume?: number
  /** Volumen lineal (no dB) de la narración, 1.0 = sin cambios. */
  narration_volume?: number
  /** Textos superpuestos posicionables en el editor (ver RM-28). */
  text_overlays?: TextOverlay[]
  /** Posición del caption (fracción 0-1, centro), arrastrable en el editor
   * igual que un overlay de texto. */
  caption_x?: number
  caption_y?: number
  /** Encuadre (pan/zoom) elegido por el usuario para cada imagen, paralelo a
   * `imageFiles` -- mismo orden, mismo índice (ver RM-30). */
  image_adjustments?: ImageAdjustment[]
}

export type CaptionHighlightStyle = 'background' | 'text_color' | 'karaoke'

/** Un texto libre superpuesto al micro-video, posicionado a mano por el
 * usuario (ver RM-28). `x`/`y` son fracciones 0-1 del ancho/alto del video
 * -- el CENTRO del texto, no la esquina. */
export interface TextOverlay {
  id: string
  text: string
  x: number
  y: number
  bold: boolean
  font_family: string
  font_size: number
  color: string
  fade: boolean
}

/** Encuadre (pan/zoom) de una imagen del micro-video, elegido a mano por el
 * usuario en el editor (ver RM-30). `offset_x`/`offset_y` son fracciones
 * 0-1 de cuánto se desplaza la ventana de recorte (0 = borde
 * superior/izquierdo visible, 1 = borde inferior/derecho visible); `zoom`
 * >= 1.0 acerca la imagen antes de recortarla. Defaults (0.5, 0.5, 1.0)
 * reproducen el recorte centrado sin zoom manual (comportamiento previo). */
export interface ImageAdjustment {
  offset_x: number
  offset_y: number
  zoom: number
  /** Estilo de color preestablecido (ver RM-31) -- 'none' = imagen original. */
  filter_preset: FilterPreset
}

/** Estilos de color preestablecidos para imágenes del micro-video (ver
 * RM-31) -- basados en los presets más usados en editores de video cortos
 * (VSCO/CapCut/Lightroom). */
export type FilterPreset = 'none' | 'sepia' | 'bw' | 'cool' | 'warm' | 'dramatic'
