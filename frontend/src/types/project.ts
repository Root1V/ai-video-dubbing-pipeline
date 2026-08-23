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

export interface ProjectStatusResponse {
  db_status: ProjectStatus
  run_id: string | null
  completed: boolean
  current_stage: string | null
  stages: ProjectStage[] | Record<string, unknown> | null
  total_seconds: number | null
  realtime_factor: number | null
  warnings: string[] | null
}

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
