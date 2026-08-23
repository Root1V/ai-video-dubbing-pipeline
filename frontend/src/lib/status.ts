import type { BadgeVariant } from '../components/ui/Badge'
import type { ProjectStatus } from '../types/project'

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  queued: 'En cola',
  downloading: 'Descargando',
  running: 'Procesando',
  completed: 'Completado',
  failed: 'Fallido',
}

export const PROJECT_STATUS_BADGE_VARIANT: Record<ProjectStatus, BadgeVariant> = {
  queued: 'warning',
  downloading: 'warning',
  running: 'warning',
  completed: 'success',
  failed: 'destructive',
}

export const ACTIVE_PROJECT_STATUSES: ProjectStatus[] = [
  'queued',
  'downloading',
  'running',
]

export function isActiveStatus(status: ProjectStatus): boolean {
  return ACTIVE_PROJECT_STATUSES.includes(status)
}
