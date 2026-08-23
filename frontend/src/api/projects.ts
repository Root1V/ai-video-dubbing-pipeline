import { apiClient } from './client'
import type {
  CreateDubbingProjectInput,
  DownloadArtifact,
  Project,
  ProjectListParams,
  ProjectListResponse,
  ProjectStatusResponse,
} from '../types/project'

export async function fetchProjects(
  params: ProjectListParams,
): Promise<ProjectListResponse> {
  const { data } = await apiClient.get<ProjectListResponse>('/projects', {
    params,
  })
  return data
}

export async function fetchProject(id: string): Promise<Project> {
  const { data } = await apiClient.get<Project>(`/projects/${id}`)
  return data
}

export async function fetchProjectStatus(
  id: string,
): Promise<ProjectStatusResponse> {
  const { data } = await apiClient.get<ProjectStatusResponse>(
    `/projects/${id}/status`,
  )
  return data
}

export async function deleteProject(id: string): Promise<void> {
  await apiClient.delete(`/projects/${id}`)
}

export async function resumeProject(id: string): Promise<Project> {
  const { data } = await apiClient.post<Project>(`/projects/${id}/resume`)
  return data
}

const ARTIFACT_FILENAME_FALLBACK: Record<DownloadArtifact, string> = {
  video: 'video.mp4',
  srt_source: 'subtitles.en.srt',
  srt_target: 'subtitles.es.srt',
}

/**
 * Downloads an artifact through the authenticated axios instance (a plain
 * `<a href="/api/...">` can't carry the Bearer token) and saves it via a
 * temporary object URL + anchor click.
 */
export async function downloadProjectArtifact(
  id: string,
  artifact: DownloadArtifact,
): Promise<void> {
  const response = await apiClient.get(`/projects/${id}/download/${artifact}`, {
    responseType: 'blob',
  })
  const contentDisposition = String(response.headers['content-disposition'] ?? '')
  const filenameMatch = /filename="?([^"]+)"?/.exec(contentDisposition)
  const filename = filenameMatch?.[1] ?? ARTIFACT_FILENAME_FALLBACK[artifact]

  const blobUrl = window.URL.createObjectURL(response.data as Blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(blobUrl)
}

export async function createDubbingProject(
  input: CreateDubbingProjectInput,
  onUploadProgress?: (percent: number) => void,
): Promise<Project> {
  const formData = new FormData()
  formData.set('name', input.name)
  formData.set('service_type', 'dubbing')
  formData.set('output_mode', 'dubbed')
  formData.set('file', input.file)
  formData.set('context_prompt', input.context_prompt ?? '')
  formData.set('tone', input.tone ?? '')
  formData.set('glossary', JSON.stringify(input.glossary ?? {}))
  formData.set('source_lang', input.source_lang ?? 'en')
  formData.set('target_lang', input.target_lang ?? 'es')
  formData.set('diarize', String(input.diarize ?? false))
  if (input.diarize) {
    if (input.min_speakers !== undefined) {
      formData.set('min_speakers', String(input.min_speakers))
    }
    if (input.max_speakers !== undefined) {
      formData.set('max_speakers', String(input.max_speakers))
    }
  }

  const { data } = await apiClient.post<Project>('/projects', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (!onUploadProgress || !event.total) return
      onUploadProgress(Math.round((event.loaded / event.total) * 100))
    },
  })
  return data
}
