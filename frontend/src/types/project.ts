export type ServiceType = 'dubbing' | 'subtitles' | 'transcription'

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

export type DownloadArtifact = 'video' | 'srt_source' | 'srt_target'

export interface GlossaryEntry {
  term: string
  translation: string
}

export interface CreateDubbingProjectInput {
  name: string
  file: File
  context_prompt?: string
  tone?: string
  glossary?: Record<string, string>
  source_lang?: string
  target_lang?: string
  diarize?: boolean
  min_speakers?: number
  max_speakers?: number
}
