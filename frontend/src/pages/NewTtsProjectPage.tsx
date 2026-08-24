import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import axios from 'axios'
import { FileAudio, UploadCloud, X } from 'lucide-react'
import { createTtsProject } from '../api/projects'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { cn } from '../lib/cn'
import { formatBytes } from '../lib/format'
import { LANGUAGE_NAMES } from '../lib/labels'

const LANGUAGE_OPTIONS = Object.entries(LANGUAGE_NAMES).map(([code, name]) => ({
  value: code,
  label: name.charAt(0).toUpperCase() + name.slice(1),
}))

export function NewTtsProjectPage() {
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const [targetLang, setTargetLang] = useState('es')
  const [voiceFile, setVoiceFile] = useState<File | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'audio/*': [] },
    multiple: false,
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0]
      if (selected) setVoiceFile(selected)
    },
  })

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!text.trim()) {
      setError('Escribe el texto que quieres convertir a voz.')
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
      const project = await createTtsProject(
        {
          name: name.trim(),
          text: text.trim(),
          target_lang: targetLang,
          voiceFile: voiceFile ?? undefined,
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
        <h1 className="text-xl font-semibold">Nuevo texto a voz</h1>
        <p className="text-sm text-muted-foreground">
          Escribe un texto y conviértelo en audio narrado.
        </p>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
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
                placeholder="Mi audio narrado"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="text" className="text-sm font-medium">
                Texto
              </label>
              <Textarea
                id="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Escribe aquí el texto que quieres narrar…"
                rows={8}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="target-lang" className="text-sm font-medium">
                Idioma del audio
              </label>
              <Select
                id="target-lang"
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
              >
                {LANGUAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Voz de referencia (opcional)</span>
              <p className="text-xs text-muted-foreground">
                Sube un audio de 6-15s con la voz a clonar. Si no subes nada, se usa una voz por defecto.
              </p>
              {!voiceFile ? (
                <div
                  {...getRootProps()}
                  className={cn(
                    'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-8 text-center transition-colors',
                    isDragActive && 'border-primary bg-primary/5',
                  )}
                >
                  <input {...getInputProps()} />
                  <UploadCloud className="h-5 w-5 text-primary" />
                  <p className="text-sm text-muted-foreground">
                    Arrastra un .wav/.mp3 aquí o haz clic para seleccionarlo
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-4 rounded-xl border border-border p-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <FileAudio className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{voiceFile.name}</p>
                    <p className="text-sm text-muted-foreground">{formatBytes(voiceFile.size)}</p>
                  </div>
                  {!isSubmitting && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => setVoiceFile(null)}
                      aria-label="Quitar voz de referencia"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              )}
            </div>

            {uploadProgress !== null && (
              <div>
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
            {isSubmitting ? 'Creando proyecto…' : 'Generar audio'}
          </Button>
        </div>
      </form>
    </div>
  )
}
