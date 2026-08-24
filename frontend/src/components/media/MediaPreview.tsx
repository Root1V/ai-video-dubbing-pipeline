import { useProjectArtifactUrl } from '../../hooks/useProjectArtifactUrl'
import type { DownloadArtifact } from '../../types/project'
import { VideoPreview } from './VideoPreview'
import { AudioWaveformPlayer } from './AudioWaveformPlayer'

interface MediaPreviewProps {
  projectId: string
  artifact: DownloadArtifact
  kind: 'video' | 'audio'
}

/** Previews a generated video/audio artifact inline, before the user
 * downloads it -- fetched as an authenticated blob (see
 * useProjectArtifactUrl) since a plain <video src="/api/..."> can't carry
 * the Bearer token. Fails silently (renders nothing) so a preview glitch
 * never blocks the download button that sits right below it. */
export function MediaPreview({ projectId, artifact, kind }: MediaPreviewProps) {
  const { url, isLoading, error } = useProjectArtifactUrl(projectId, artifact, true)

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Cargando vista previa…</p>
  }
  if (error || !url) {
    return null
  }
  return kind === 'video' ? <VideoPreview src={url} /> : <AudioWaveformPlayer src={url} />
}
