import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createSubtitlesProject } from '../api/projects'
import type { CreateSubtitlesProjectInput } from '../types/project'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { GlossaryEditor } from '../components/GlossaryEditor'
import type { GlossaryRow } from '../components/GlossaryEditor'
import { MediaSourceInput } from '../components/media/MediaSourceInput'
import { cn } from '../lib/cn'
import { getErrorMessage } from '../lib/errors'
import { OUTPUT_MODE_LABELS } from '../lib/labels'

const TONE_OPTIONS = [
  { value: '', label: 'Sin preferencia' },
  { value: 'formal', label: 'Formal' },
  { value: 'informal', label: 'Informal' },
  { value: 'tecnico', label: 'Técnico' },
]

const OUTPUT_MODE_OPTIONS: {
  value: CreateSubtitlesProjectInput['output_mode']
  description: string
}[] = [
  { value: 'subtitles_only', description: 'Solo el archivo .srt, sin renderizar video.' },
  { value: 'burn_subtitles', description: 'Quemados en el video, siempre visibles.' },
  { value: 'soft_subtitles', description: 'Pista independiente que se puede activar/desactivar.' },
]

function stripExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  return lastDot > 0 ? filename.slice(0, lastDot) : filename
}

export function NewSubtitlesProjectPage() {
  const navigate = useNavigate()

  const [file, setFile] = useState<File | null>(null)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [outputMode, setOutputMode] =
    useState<CreateSubtitlesProjectInput['output_mode']>('subtitles_only')
  const [contextPrompt, setContextPrompt] = useState('')
  const [tone, setTone] = useState('')
  const [glossaryRows, setGlossaryRows] = useState<GlossaryRow[]>([])

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  function handleFileChange(selected: File | null) {
    setFile(selected)
    if (selected && !name) {
      setName(stripExtension(selected.name))
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file && !sourceUrl) {
      setError('Selecciona un archivo de video o pega una URL para continuar.')
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
      const project = await createSubtitlesProject(
        {
          name: name.trim(),
          file: file ?? undefined,
          source_url: sourceUrl ?? undefined,
          output_mode: outputMode,
          context_prompt: contextPrompt,
          tone,
          glossary,
        },
        setUploadProgress,
      )
      navigate(`/projects/${project.id}`)
    } catch (err) {
      setError(getErrorMessage(err, 'No se pudo crear el proyecto. Intenta de nuevo.'))
      setIsSubmitting(false)
      setUploadProgress(null)
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Nuevos subtítulos</h1>
        <p className="text-sm text-muted-foreground">
          Sube un video para generar subtítulos traducidos.
        </p>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <MediaSourceInput
          file={file}
          onFileChange={handleFileChange}
          sourceUrl={sourceUrl}
          onSourceUrlChange={setSourceUrl}
          accept={{ 'video/*': [] }}
          dropTitle="Arrastra tu video aquí o haz clic para seleccionarlo"
          dropSubtitle="Formatos de video compatibles (MP4, MOV, MKV, etc.)"
          uploadProgress={uploadProgress}
          disabled={isSubmitting}
        />

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
                placeholder="Mis subtítulos"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Modo de salida</span>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {OUTPUT_MODE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setOutputMode(option.value)}
                    className={cn(
                      'flex flex-col items-start gap-0.5 rounded-xl border p-3 text-left transition-colors',
                      outputMode === option.value
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-secondary/50',
                    )}
                  >
                    <span className="text-sm font-medium">{OUTPUT_MODE_LABELS[option.value]}</span>
                    <span className="text-xs text-muted-foreground">{option.description}</span>
                  </button>
                ))}
              </div>
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
            {isSubmitting ? 'Creando proyecto…' : 'Generar subtítulos'}
          </Button>
        </div>
      </form>
    </div>
  )
}
