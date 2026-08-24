import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { DownloadArtifact } from '../types/project'

interface ProjectArtifactUrlState {
  url: string | null
  isLoading: boolean
  error: boolean
}

/**
 * Fetches a project artifact (video/audio) as a Blob through the
 * authenticated axios instance -- a plain `<video src="/api/...">` can't
 * carry the Bearer token, same reason `downloadProjectArtifact` in
 * api/projects.ts fetches as a blob instead of linking directly. Returns an
 * object URL a <video>/<audio> element can play, and revokes it on
 * unmount/artifact change so it doesn't leak memory.
 */
export function useProjectArtifactUrl(
  projectId: string,
  artifact: DownloadArtifact,
  enabled: boolean,
): ProjectArtifactUrlState {
  const [state, setState] = useState<ProjectArtifactUrlState>({
    url: null,
    isLoading: enabled,
    error: false,
  })

  useEffect(() => {
    if (!enabled) return
    let objectUrl: string | null = null
    let cancelled = false

    setState({ url: null, isLoading: true, error: false })
    apiClient
      .get(`/projects/${projectId}/download/${artifact}`, { responseType: 'blob' })
      .then((response) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(response.data as Blob)
        setState({ url: objectUrl, isLoading: false, error: false })
      })
      .catch(() => {
        if (!cancelled) setState({ url: null, isLoading: false, error: true })
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [projectId, artifact, enabled])

  return state
}
