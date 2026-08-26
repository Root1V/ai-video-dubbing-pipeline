import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createTranscriptionProject } from '../api/projects'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { MediaSourceInput } from '../components/media/MediaSourceInput'
import { getErrorMessage } from '../lib/errors'
import { LANGUAGE_NAMES } from '../lib/labels'

const LANGUAGE_OPTIONS = [
  { value: '', label: 'Detectar automáticamente' },
  ...Object.entries(LANGUAGE_NAMES).map(([code, name]) => ({
    value: code,
    label: name.charAt(0).toUpperCase() + name.slice(1),
  })),
]

function stripExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  return lastDot > 0 ? filename.slice(0, lastDot) : filename
}

export function NewTranscriptionProjectPage() {
  const navigate = useNavigate()

  const [file, setFile] = useState<File | null>(null)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [sourceUrlValidated, setSourceUrlValidated] = useState(false)
  const [name, setName] = useState('')
  const [sourceLang, setSourceLang] = useState('')

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
      setError('Selecciona un archivo de audio/video o pega una URL para continuar.')
      return
    }
    if (sourceUrl && !sourceUrlValidated) {
      setError('Espera a que la URL se valide antes de continuar.')
      return
    }
    if (!name.trim()) {
      setError('Ingresa un nombre para el proyecto.')
      return
    }

    setError(null)
    setIsSubmitting(true)
    setUploadProgress(0)

    try {
      const project = await createTranscriptionProject(
        {
          name: name.trim(),
          file: file ?? undefined,
          source_url: sourceUrl ?? undefined,
          source_lang: sourceLang,
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
        <h1 className="text-xl font-semibold">Nueva transcripción</h1>
        <p className="text-sm text-muted-foreground">
          Sube un audio o video para obtener su transcripción en el idioma original.
        </p>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <MediaSourceInput
          file={file}
          onFileChange={handleFileChange}
          sourceUrl={sourceUrl}
          onSourceUrlChange={setSourceUrl}
          onSourceUrlValidatedChange={setSourceUrlValidated}
          accept={{ 'video/*': [], 'audio/*': [] }}
          dropTitle="Arrastra tu archivo aquí o haz clic para seleccionarlo"
          dropSubtitle="Video o audio (MP4, MOV, MKV, MP3, WAV, M4A, FLAC…)"
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
                placeholder="Mi transcripción"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="source-lang" className="text-sm font-medium">
                Idioma del audio
              </label>
              <Select
                id="source-lang"
                value={sourceLang}
                onChange={(e) => setSourceLang(e.target.value)}
              >
                {LANGUAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
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
          <Button
            type="submit"
            disabled={isSubmitting || (Boolean(sourceUrl) && !sourceUrlValidated)}
          >
            {isSubmitting ? 'Creando proyecto…' : 'Transcribir'}
          </Button>
        </div>
      </form>
    </div>
  )
}
