import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { createMicroVideoProject } from '../api/projects'
import { fetchMusicTracks } from '../api/musicTracks'
import { fetchMusicSampleUrl } from '../api/samples'
import { TextOverlayCanvas } from '../components/media/TextOverlayCanvas'
import { EditorBottomTracks } from '../components/microVideoEditor/EditorBottomTracks'
import { EditorLeftToolbar } from '../components/microVideoEditor/EditorLeftToolbar'
import { EditorRightPanel } from '../components/microVideoEditor/EditorRightPanel'
import { EditorTopBar } from '../components/microVideoEditor/EditorTopBar'
import type { EditorTool } from '../components/microVideoEditor/types'
import { Alert } from '../components/ui/Alert'
import { getErrorMessage } from '../lib/errors'
import type { CaptionHighlightStyle, TextOverlay, TtsVoiceOption } from '../types/project'

function makeOverlay(): TextOverlay {
  return {
    id: crypto.randomUUID(),
    text: '',
    x: 0.5,
    y: 0.5,
    bold: false,
    font_family: 'Arial',
    font_size: 64,
    color: '#FFFFFF',
    fade: false,
  }
}

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
  const [backgroundMusic, setBackgroundMusic] = useState<string | null>(null)
  const [musicStart, setMusicStart] = useState(0)
  const [musicEnd, setMusicEnd] = useState<number | undefined>(undefined)
  const [musicPreviewUrl, setMusicPreviewUrl] = useState<string | null>(null)
  const [textOverlays, setTextOverlays] = useState<TextOverlay[]>([])
  const [selectedOverlayId, setSelectedOverlayId] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [activeTool, setActiveTool] = useState<EditorTool>('image')

  const { data: musicTracks = [] } = useQuery({
    queryKey: ['music-tracks'],
    queryFn: () => fetchMusicTracks(),
  })

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  useEffect(() => {
    if (!imageFile) {
      setImageUrl(null)
      return
    }
    const url = URL.createObjectURL(imageFile)
    setImageUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [imageFile])

  useEffect(() => {
    setMusicStart(0)
    setMusicEnd(undefined)
    if (!backgroundMusic) {
      setMusicPreviewUrl(null)
      return
    }
    let cancelled = false
    let objectUrl: string | null = null
    fetchMusicSampleUrl(backgroundMusic).then((url) => {
      if (cancelled) {
        URL.revokeObjectURL(url)
        return
      }
      objectUrl = url
      setMusicPreviewUrl(url)
    })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [backgroundMusic])

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
          background_music: backgroundMusic ?? undefined,
          background_music_start: backgroundMusic ? musicStart : undefined,
          background_music_end: backgroundMusic ? musicEnd : undefined,
          text_overlays: textOverlays,
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
    <form onSubmit={handleSubmit} className="flex h-full flex-col">
      <EditorTopBar
        name={name}
        onNameChange={setName}
        onCancel={() => navigate('/')}
        isSubmitting={isSubmitting}
        uploadProgress={uploadProgress}
      />

      {error && (
        <div className="shrink-0 px-4 pt-3">
          <Alert variant="error" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <EditorLeftToolbar activeTool={activeTool} onSelect={setActiveTool} />

        <div className="flex flex-1 items-center justify-center overflow-y-auto p-6">
          {imageUrl ? (
            <TextOverlayCanvas
              imageUrl={imageUrl}
              overlays={textOverlays}
              selectedId={selectedOverlayId}
              onSelect={(id) => {
                setSelectedOverlayId(id)
                setActiveTool('text')
              }}
              onMove={(id, x, y) =>
                setTextOverlays((prev) => prev.map((o) => (o.id === id ? { ...o, x, y } : o)))
              }
            />
          ) : (
            <p className="max-w-xs text-center text-sm text-muted-foreground">
              Sube una imagen desde la herramienta "Imagen" (a la izquierda) para empezar a editar.
            </p>
          )}
        </div>

        <EditorRightPanel
          activeTool={activeTool}
          isSubmitting={isSubmitting}
          imageFile={imageFile}
          onImageFileSelected={setImageFile}
          onImageRemove={() => setImageFile(null)}
          hasImage={Boolean(imageUrl)}
          overlays={textOverlays}
          selectedOverlayId={selectedOverlayId}
          onAddOverlay={() => {
            const overlay = makeOverlay()
            setTextOverlays((prev) => [...prev, overlay])
            setSelectedOverlayId(overlay.id)
          }}
          onChangeOverlay={(updated) =>
            setTextOverlays((prev) => prev.map((o) => (o.id === updated.id ? updated : o)))
          }
          onRemoveOverlay={(id) => {
            setTextOverlays((prev) => prev.filter((o) => o.id !== id))
            setSelectedOverlayId(null)
          }}
          text={text}
          onTextChange={setText}
          targetLang={targetLang}
          onTargetLangChange={setTargetLang}
          targetDuration={targetDuration}
          onTargetDurationChange={setTargetDuration}
          voiceOption={voiceOption}
          onVoiceOptionChange={setVoiceOption}
          voiceFile={voiceFile}
          onVoiceFileSelected={setVoiceFile}
          onRemoveVoiceFile={() => setVoiceFile(null)}
          musicTracks={musicTracks}
          backgroundMusic={backgroundMusic}
          onSelectMusic={setBackgroundMusic}
          highlightStyle={highlightStyle}
          onHighlightStyleChange={setHighlightStyle}
          captionBgColor={captionBgColor}
          onCaptionBgColorChange={setCaptionBgColor}
        />
      </div>

      <EditorBottomTracks
        narrationText={text}
        onNarrationClick={() => setActiveTool('narration')}
        hasMusic={backgroundMusic !== null}
        musicPreviewUrl={musicPreviewUrl}
        musicKey={backgroundMusic}
        onMusicClick={() => setActiveTool('music')}
        onRangeChange={(start, end) => {
          setMusicStart(start)
          setMusicEnd(end)
        }}
      />
    </form>
  )
}
