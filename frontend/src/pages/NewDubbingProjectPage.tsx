import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import axios from 'axios'
import { Clapperboard, FileVideo, UploadCloud, X } from 'lucide-react'
import { createDubbingProject } from '../api/projects'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Select } from '../components/ui/Select'
import { Switch } from '../components/ui/Switch'
import { Alert } from '../components/ui/Alert'
import { GlossaryEditor } from '../components/GlossaryEditor'
import type { GlossaryRow } from '../components/GlossaryEditor'
import { cn } from '../lib/cn'
import { formatBytes } from '../lib/format'

const TONE_OPTIONS = [
  { value: '', label: 'Sin preferencia' },
  { value: 'formal', label: 'Formal' },
  { value: 'informal', label: 'Informal' },
  { value: 'tecnico', label: 'Técnico' },
]

function stripExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  return lastDot > 0 ? filename.slice(0, lastDot) : filename
}

export function NewDubbingProjectPage() {
  const navigate = useNavigate()

  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [contextPrompt, setContextPrompt] = useState('')
  const [tone, setTone] = useState('')
  const [glossaryRows, setGlossaryRows] = useState<GlossaryRow[]>([])
  const [diarize, setDiarize] = useState(false)
  const [minSpeakers, setMinSpeakers] = useState<number>(2)
  const [maxSpeakers, setMaxSpeakers] = useState<number>(4)

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'video/*': [] },
    multiple: false,
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0]
      if (!selected) return
      setFile(selected)
      if (!name) {
        setName(stripExtension(selected.name))
      }
    },
  })

  function removeFile() {
    setFile(null)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setError('Selecciona un archivo de video para continuar.')
      return
    }
    if (!name.trim()) {
      setError('Ingresa un nombre para el proyecto.')
      return
    }

    setError(null)
    setIsSubmitting(true)
    setUploadProgress(0)

    const glossary = glossaryRows.reduce<Record<string, string>>((acc, row) => {
      if (row.term.trim()) {
        acc[row.term.trim()] = row.translation
      }
      return acc
    }, {})

    try {
      const project = await createDubbingProject(
        {
          name: name.trim(),
          file,
          context_prompt: contextPrompt,
          tone,
          glossary,
          diarize,
          min_speakers: diarize ? minSpeakers : undefined,
          max_speakers: diarize ? maxSpeakers : undefined,
        },
        setUploadProgress,
      )
      navigate(`/projects/${project.id}`)
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(
          (err.response?.data as { detail?: string } | undefined)?.detail ??
            'No se pudo crear el proyecto. Intenta de nuevo.',
        )
      } else {
        setError('No se pudo crear el proyecto. Intenta de nuevo.')
      }
      setIsSubmitting(false)
      setUploadProgress(null)
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Nuevo doblaje de video</h1>
        <p className="text-sm text-muted-foreground">
          Sube un video para traducirlo y doblarlo automáticamente.
        </p>
      </div>

      <div className="flex border-b border-border">
        <button
          type="button"
          className="border-b-2 border-primary px-4 py-2 text-sm font-medium text-primary"
        >
          Subir archivo
        </button>
        <button
          type="button"
          disabled
          className="flex cursor-not-allowed items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground/60"
        >
          <Clapperboard className="h-4 w-4" />
          Buscar en YouTube
          <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
            Próximamente
          </span>
        </button>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {!file ? (
          <div
            {...getRootProps()}
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-14 text-center transition-colors',
              isDragActive && 'border-primary bg-primary/5',
            )}
          >
            <input {...getInputProps()} />
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <UploadCloud className="h-6 w-6" />
            </div>
            <div>
              <p className="font-medium">
                Arrastra tu video aquí o haz clic para seleccionarlo
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Formatos de video compatibles (MP4, MOV, MKV, etc.)
              </p>
            </div>
          </div>
        ) : (
          <Card>
            <CardContent className="flex items-center gap-4 p-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <FileVideo className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{file.name}</p>
                <p className="text-sm text-muted-foreground">
                  {formatBytes(file.size)}
                </p>
              </div>
              {!isSubmitting && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={removeFile}
                  aria-label="Quitar archivo"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </CardContent>
            {uploadProgress !== null && (
              <CardContent className="pt-0">
                <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {uploadProgress < 100
                    ? `Subiendo… ${uploadProgress}%`
                    : 'Subida completa, creando proyecto…'}
                </p>
              </CardContent>
            )}
          </Card>
        )}

        <Card>
          <CardContent className="flex flex-col gap-5 p-6">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="name" className="text-sm font-medium">
                Nombre del proyecto
              </label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Mi video doblado"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="context" className="text-sm font-medium">
                Contexto
              </label>
              <Textarea
                id="context"
                value={contextPrompt}
                onChange={(e) => setContextPrompt(e.target.value)}
                placeholder="Describe el tema o contexto del video para mejorar la traducción…"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="tone" className="text-sm font-medium">
                Tono
              </label>
              <Select
                id="tone"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
              >
                {TONE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Glosario</span>
              <p className="text-xs text-muted-foreground">
                Define términos que deben traducirse siempre de la misma forma.
              </p>
              <GlossaryEditor rows={glossaryRows} onChange={setGlossaryRows} />
            </div>

            <div className="flex items-center justify-between rounded-xl border border-border p-4">
              <div>
                <p className="text-sm font-medium">
                  Detectar múltiples hablantes (diarización)
                </p>
                <p className="text-xs text-muted-foreground">
                  Identifica distintos hablantes y asigna una voz a cada uno.
                </p>
              </div>
              <Switch checked={diarize} onCheckedChange={setDiarize} />
            </div>

            {diarize && (
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="min-speakers" className="text-sm font-medium">
                    Mínimo de hablantes
                  </label>
                  <Input
                    id="min-speakers"
                    type="number"
                    min={1}
                    value={minSpeakers}
                    onChange={(e) => setMinSpeakers(Number(e.target.value))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="max-speakers" className="text-sm font-medium">
                    Máximo de hablantes
                  </label>
                  <Input
                    id="max-speakers"
                    type="number"
                    min={1}
                    value={maxSpeakers}
                    onChange={(e) => setMaxSpeakers(Number(e.target.value))}
                  />
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/')}
            disabled={isSubmitting}
          >
            Cancelar
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creando proyecto…' : 'Iniciar doblaje'}
          </Button>
        </div>
      </form>
    </div>
  )
}
