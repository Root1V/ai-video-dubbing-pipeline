import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react'
import { deleteProject, fetchProject, fetchProjectStatus } from '../api/projects'
import type { ProjectStage, ProjectStatus } from '../types/project'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { formatDateTime } from '../lib/format'
import { PROJECT_STATUS_BADGE_VARIANT, PROJECT_STATUS_LABELS, isActiveStatus } from '../lib/status'
import { OUTPUT_MODE_LABELS, SERVICE_TYPE_LABELS } from '../lib/labels'

const FALLBACK_MESSAGES: Record<ProjectStatus, (errorMessage: string | null) => string> = {
  queued: () => 'En cola',
  downloading: () => 'Descargando',
  running: () => 'Procesando…',
  completed: () => 'Completado',
  failed: (errorMessage) => `Falló: ${errorMessage ?? 'error desconocido'}`,
}

function normalizeStages(
  stages: ProjectStage[] | Record<string, unknown> | null,
): ProjectStage[] {
  if (!stages) return []
  if (Array.isArray(stages)) return stages
  return Object.entries(stages).map(([name, value]) => ({
    name,
    ...(typeof value === 'object' && value !== null ? value : { status: String(value) }),
  }))
}

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const projectQuery = useQuery({
    queryKey: ['projects', id],
    queryFn: () => fetchProject(id as string),
    enabled: Boolean(id),
  })

  const statusQuery = useQuery({
    queryKey: ['projects', id, 'status'],
    queryFn: () => fetchProjectStatus(id as string),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const dbStatus = query.state.data?.db_status
      return dbStatus && isActiveStatus(dbStatus) ? 3000 : false
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(id as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate('/projects')
    },
  })

  function handleDelete() {
    if (window.confirm('¿Seguro que quieres eliminar este proyecto? Esta acción no se puede deshacer.')) {
      deleteMutation.mutate()
    }
  }

  if (projectQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Cargando proyecto…</p>
  }

  if (projectQuery.isError || !projectQuery.data) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <p className="text-sm text-muted-foreground">No se pudo cargar el proyecto.</p>
        <Button variant="outline" onClick={() => navigate('/projects')}>
          Volver a proyectos
        </Button>
      </div>
    )
  }

  const project = projectQuery.data
  const status = statusQuery.data
  const dbStatus = status?.db_status ?? project.status
  const stages = normalizeStages(status?.stages ?? null)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <button
        type="button"
        onClick={() => navigate('/projects')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Volver a proyectos
      </button>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">{project.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{SERVICE_TYPE_LABELS[project.service_type]}</Badge>
            <Badge variant="outline">{OUTPUT_MODE_LABELS[project.output_mode]}</Badge>
            <Badge variant={PROJECT_STATUS_BADGE_VARIANT[dbStatus]}>
              {isActiveStatus(dbStatus) && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
              {PROJECT_STATUS_LABELS[dbStatus]}
            </Badge>
          </div>
        </div>
        <Button
          variant="destructive"
          size="sm"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
        >
          <Trash2 className="h-4 w-4" />
          Eliminar
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Progreso</CardTitle>
        </CardHeader>
        <CardContent>
          {stages.length > 0 ? (
            <ul className="flex flex-col gap-2">
              {stages.map((stage) => (
                <li
                  key={stage.name}
                  className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <span
                    className={
                      stage.name === status?.current_stage
                        ? 'font-medium text-primary'
                        : ''
                    }
                  >
                    {stage.name}
                  </span>
                  {stage.status && (
                    <span className="text-muted-foreground">{String(stage.status)}</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              {FALLBACK_MESSAGES[dbStatus](project.error_message)}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Detalles</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                Creado
              </dt>
              <dd className="mt-1 text-sm">{formatDateTime(project.created_at)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                Iniciado
              </dt>
              <dd className="mt-1 text-sm">{formatDateTime(project.started_at)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                Completado
              </dt>
              <dd className="mt-1 text-sm">{formatDateTime(project.completed_at)}</dd>
            </div>
            {status && (
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                  Factor tiempo real
                </dt>
                <dd className="mt-1 text-sm">
                  {status.realtime_factor !== null ? status.realtime_factor.toFixed(2) : '—'}
                </dd>
              </div>
            )}
          </dl>

          {status?.warnings && status.warnings.length > 0 && (
            <div className="mt-4 flex flex-col gap-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Advertencias
              </p>
              <ul className="list-inside list-disc text-sm text-warning">
                {status.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          {project.error_message && dbStatus === 'failed' && (
            <p className="mt-4 text-sm text-destructive">{project.error_message}</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
