import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchProjects } from '../api/projects'
import type { ProjectStatus, ServiceType } from '../types/project'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Select } from '../components/ui/Select'
import { Button } from '../components/ui/Button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/Table'
import { formatDateTime } from '../lib/format'
import { PROJECT_STATUS_BADGE_VARIANT, PROJECT_STATUS_LABELS } from '../lib/status'
import { OUTPUT_MODE_LABELS, SERVICE_TYPE_LABELS } from '../lib/labels'

const PAGE_SIZE = 20

const STATUS_FILTER_OPTIONS: { value: ProjectStatus | ''; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'queued', label: PROJECT_STATUS_LABELS.queued },
  { value: 'downloading', label: PROJECT_STATUS_LABELS.downloading },
  { value: 'running', label: PROJECT_STATUS_LABELS.running },
  { value: 'completed', label: PROJECT_STATUS_LABELS.completed },
  { value: 'failed', label: PROJECT_STATUS_LABELS.failed },
]

const SERVICE_FILTER_OPTIONS: { value: ServiceType | ''; label: string }[] = [
  { value: '', label: 'Todos los servicios' },
  { value: 'dubbing', label: SERVICE_TYPE_LABELS.dubbing },
  { value: 'subtitles', label: SERVICE_TYPE_LABELS.subtitles },
  { value: 'transcription', label: SERVICE_TYPE_LABELS.transcription },
]

export function ProjectsListPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<ProjectStatus | ''>('')
  const [serviceType, setServiceType] = useState<ServiceType | ''>('')
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['projects', { status, service_type: serviceType, page, page_size: PAGE_SIZE }],
    queryFn: () =>
      fetchProjects({
        status: status || undefined,
        service_type: serviceType || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  })

  const projects = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function handleStatusChange(value: string) {
    setStatus(value as ProjectStatus | '')
    setPage(1)
  }

  function handleServiceTypeChange(value: string) {
    setServiceType(value as ServiceType | '')
    setPage(1)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Proyectos</h1>
          <p className="text-sm text-muted-foreground">
            Todos tus proyectos de doblaje, subtítulos y transcripción.
          </p>
        </div>
        <Button onClick={() => navigate('/dubbing/new')}>Nuevo proyecto</Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="w-52">
          <Select
            value={status}
            onChange={(e) => handleStatusChange(e.target.value)}
          >
            {STATUS_FILTER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-52">
          <Select
            value={serviceType}
            onChange={(e) => handleServiceTypeChange(e.target.value)}
          >
            {SERVICE_FILTER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <p className="p-6 text-sm text-muted-foreground">Cargando…</p>
          ) : projects.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <p className="text-sm text-muted-foreground">
                No se encontraron proyectos con estos filtros
              </p>
              <Button onClick={() => navigate('/dubbing/new')}>
                Crear un proyecto
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Servicio</TableHead>
                  <TableHead>Modo</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Creado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((project) => (
                  <TableRow
                    key={project.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/projects/${project.id}`)}
                  >
                    <TableCell className="font-medium">{project.name}</TableCell>
                    <TableCell>{SERVICE_TYPE_LABELS[project.service_type]}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {OUTPUT_MODE_LABELS[project.output_mode]}
                    </TableCell>
                    <TableCell>
                      <Badge variant={PROJECT_STATUS_BADGE_VARIANT[project.status]}>
                        {PROJECT_STATUS_LABELS[project.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(project.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Página {page} de {totalPages} · {total} proyecto{total === 1 ? '' : 's'}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Siguiente
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
