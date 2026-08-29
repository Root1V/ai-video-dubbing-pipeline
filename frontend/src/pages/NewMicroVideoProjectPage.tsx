import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { FileAudio, Image as ImageIcon, UploadCloud, X } from 'lucide-react'
import { createMicroVideoProject } from '../api/projects'
import type { CaptionHighlightStyle, TtsVoiceOption } from '../types/project'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { cn } from '../lib/cn'
import { getErrorMessage } from '../lib/errors'
import { formatBytes } from '../lib/format'
import { LANGUAGE_NAMES } from '../lib/labels'

const LANGUAGE_OPTIONS = Object.entries(LANGUAGE_NAMES).map(([code, name]) => ({
  value: code,
  label: name.charAt(0).toUpperCase() + name.slice(1),
}))

const VOICE_OPTIONS: { value: TtsVoiceOption; label: string; description: string }[] = [
  { value: 'public_female', label: 'Locutora', description: 'Voz pública femenina (por defecto)' },
  { value: 'public_male', label: 'Locutor', description: 'Voz pública masculina' },
  { value: 'own', label: 'Mi voz', description: 'Sube tu propia muestra de voz' },
]

// Duraciones estándar de video corto por plataforma: 15s (viral en Reels),
// 30s (Reels/TikTok), 60s (TikTok/Shorts), 90s (máximo recomendado en
// Facebook Reels). "Automático" (null) mantiene el comportamiento previo:
// el video dura lo que tarda la narración.
const DURATION_OPTIONS: { value: number | null; label: string }[] = [
  { value: null, label: 'Automático' },
  { value: 15, label: '15s' },
  { value: 30, label: '30s' },
  { value: 60, label: '60s' },
  { value: 90, label: '90s' },
]

const HIGHLIGHT_STYLE_OPTIONS: { value: CaptionHighlightStyle; label: string; description: string }[] = [
  { value: 'background', label: 'Caja de fondo', description: 'Texto blanco sobre una caja de color' },
  { value: 'text_color', label: 'Color de texto', description: 'El texto toma el color, sin caja' },
]

export function NewMicroVideoProjectPage() {
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const [targetLang, setTargetLang] = useState('es')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [voiceOption, setVoiceOption] = useState<TtsVoiceOption>('public_female')
  const [voiceFile, setVoiceFile] = useState<File | null>(null)
  const [targetDuration, setTargetDuration] = useState<number | null>(null)
  const [captionBgColor, setCaptionBgColor] = useState('#000000')
  const [highlightStyle, setHighlightStyle] = useState<CaptionHighlightStyle>('background')

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  const imageDropzone = useDropzone({
    accept: { 'image/*': [] },
    multiple: false,
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0]
      if (selected) setImageFile(selected)
    },
  })

  const voiceDropzone = useDropzone({
    accept: { 'audio/*': [] },
    multiple: false,
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0]
      if (selected) setVoiceFile(selected)
    },
  })

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) {
      setError('Ingresa un nombre para el proyecto.')
      return
    }
    if (!imageFile) {
      setError('Sube la imagen que quieres animar.')
      return
    }
    if (!text.trim()) {
      setError('Escribe el texto que quieres narrar.')
      return
    }
    if (voiceOption === 'own' && !voiceFile) {
      setError('Sube tu voz de referencia o elige una de las voces públicas.')
      return
    }

    setError(null)
    setIsSubmitting(true)
    setUploadProgress(0)

    try {
      const project = await createMicroVideoProject(
        {
          name: name.trim(),
          text: text.trim(),
          imageFile,
          target_lang: targetLang,
          voice_option: voiceOption,
          voiceFile: voiceFile ?? undefined,
          target_duration_seconds: targetDuration ?? undefined,
          caption_bg_color: captionBgColor,
          caption_highlight_style: highlightStyle,
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
        <h1 className="text-xl font-semibold">Nuevo micro-video</h1>
        <p className="text-sm text-muted-foreground">
          Sube una imagen y escribe un texto: genera un video vertical narrado, con efecto de zoom y
          captions incrustados.
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
                placeholder="Mi micro-video"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Imagen</span>
              {!imageFile ? (
                <div
                  {...imageDropzone.getRootProps()}
                  className={cn(
                    'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-8 text-center transition-colors',
                    imageDropzone.isDragActive && 'border-primary bg-primary/5',
                  )}
                >
                  <input {...imageDropzone.getInputProps()} />
                  <UploadCloud className="h-5 w-5 text-primary" />
                  <p className="text-sm text-muted-foreground">
                    Arrastra una imagen aquí o haz clic para seleccionarla
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-4 rounded-xl border border-border p-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <ImageIcon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{imageFile.name}</p>
                    <p className="text-sm text-muted-foreground">{formatBytes(imageFile.size)}</p>
                  </div>
                  {!isSubmitting && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => setImageFile(null)}
                      aria-label="Quitar imagen"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="text" className="text-sm font-medium">
                Texto a narrar
              </label>
              <Textarea
                id="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Escribe aquí el texto que se va a narrar sobre la imagen…"
                rows={6}
              />
              <p className="text-xs text-muted-foreground">
                Tip: envolvé una palabra o frase entre <code>**así**</code> para que aparezca en{' '}
                <strong>negrita</strong> en los captions (no se narra en voz alta).
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="target-lang" className="text-sm font-medium">
                Idioma de la narración
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
              <span className="text-sm font-medium">Duración del video</span>
              <div className="grid grid-cols-5 gap-2">
                {DURATION_OPTIONS.map((option) => (
                  <button
                    key={option.label}
                    type="button"
                    onClick={() => setTargetDuration(option.value)}
                    className={cn(
                      'rounded-xl border p-2 text-center text-sm font-medium transition-colors',
                      targetDuration === option.value
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-secondary/50',
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Automático: el video dura lo que tarda la narración. Con una duración fija, la
                narración se acelera si es más larga o se mantiene la imagen si es más corta.
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Resaltado de los captions</span>
              <div className="grid grid-cols-2 gap-2">
                {HIGHLIGHT_STYLE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setHighlightStyle(option.value)}
                    className={cn(
                      'flex flex-col items-start gap-0.5 rounded-xl border p-3 text-left transition-colors',
                      highlightStyle === option.value
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-secondary/50',
                    )}
                  >
                    <span className="text-sm font-medium">{option.label}</span>
                    <span className="text-xs text-muted-foreground">{option.description}</span>
                  </button>
                ))}
              </div>
              <div className="mt-2 flex items-center gap-3">
                <input
                  id="caption-bg-color"
                  type="color"
                  value={captionBgColor}
                  onChange={(e) => setCaptionBgColor(e.target.value)}
                  className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-transparent p-1"
                />
                <label htmlFor="caption-bg-color" className="text-xs text-muted-foreground">
                  {highlightStyle === 'text_color'
                    ? 'Color del texto de los captions.'
                    : 'Color de la caja de fondo -- el texto es siempre blanco.'}
                </label>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Voz</span>
              <div className="grid grid-cols-3 gap-2">
                {VOICE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setVoiceOption(option.value)}
                    className={cn(
                      'flex flex-col items-start gap-0.5 rounded-xl border p-3 text-left transition-colors',
                      voiceOption === option.value
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-secondary/50',
                    )}
                  >
                    <span className="text-sm font-medium">{option.label}</span>
                    <span className="text-xs text-muted-foreground">{option.description}</span>
                  </button>
                ))}
              </div>

              {voiceOption === 'own' &&
                (!voiceFile ? (
                  <div
                    {...voiceDropzone.getRootProps()}
                    className={cn(
                      'mt-2 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-8 text-center transition-colors',
                      voiceDropzone.isDragActive && 'border-primary bg-primary/5',
                    )}
                  >
                    <input {...voiceDropzone.getInputProps()} />
                    <UploadCloud className="h-5 w-5 text-primary" />
                    <p className="text-sm text-muted-foreground">
                      Arrastra un .wav/.mp3 aquí o haz clic para seleccionarlo (6-15s de la voz a clonar)
                    </p>
                  </div>
                ) : (
                  <div className="mt-2 flex items-center gap-4 rounded-xl border border-border p-4">
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
                ))}
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
            {isSubmitting ? 'Creando proyecto…' : 'Generar micro-video'}
          </Button>
        </div>
      </form>
    </div>
  )
}
