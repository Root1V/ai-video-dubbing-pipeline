import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { createMicroVideoProject } from '../api/projects'
import { fetchMusicTracks } from '../api/musicTracks'
import { fetchMusicSampleUrl } from '../api/samples'
import { TextOverlayCanvas } from '../components/media/TextOverlayCanvas'
import type { CaptionPreview } from '../components/media/TextOverlayCanvas'
import { EditorBottomTracks } from '../components/microVideoEditor/EditorBottomTracks'
import { EditorLeftToolbar } from '../components/microVideoEditor/EditorLeftToolbar'
import { EditorRightPanel } from '../components/microVideoEditor/EditorRightPanel'
import { EditorTopBar } from '../components/microVideoEditor/EditorTopBar'
import type { EditorTool } from '../components/microVideoEditor/types'
import { Alert } from '../components/ui/Alert'
import { getErrorMessage } from '../lib/errors'
import type { CaptionHighlightStyle, ImageAdjustment, TextOverlay, TtsVoiceOption } from '../types/project'

function makeImageAdjustment(): ImageAdjustment {
  return { offset_x: 0.5, offset_y: 0.5, zoom: 1.0 }
}

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
  const [imageFiles, setImageFiles] = useState<File[]>([])
  const [imageAdjustments, setImageAdjustments] = useState<ImageAdjustment[]>([])
  const [activeImageIndex, setActiveImageIndex] = useState(0)
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
  const [narrationVolume, setNarrationVolume] = useState(1.0)
  const [musicVolume, setMusicVolume] = useState(0.12)
  const [captionX, setCaptionX] = useState(0.5)
  const [captionY, setCaptionY] = useState(0.85)

  const { data: musicTracks = [] } = useQuery({
    queryKey: ['music-tracks'],
    queryFn: () => fetchMusicTracks(),
  })

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  useEffect(() => {
    // El lienzo muestra la imagen ACTIVA (elegida en ImagePanel, ver RM-30)
    // como referencia para posicionar overlays/subtitulos (que son
    // globales, no por-imagen -- ver RM-29) y para ajustar su encuadre.
    const activeImage = imageFiles[activeImageIndex]
    if (!activeImage) {
      setImageUrl(null)
      return
    }
    const url = URL.createObjectURL(activeImage)
    setImageUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [imageFiles, activeImageIndex])

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
    if (imageFiles.length === 0) {
      setError('Sube al menos una imagen para animar.')
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
          imageFiles,
          target_lang: targetLang,
          voice_option: voiceOption,
          voiceFile: voiceFile ?? undefined,
          target_duration_seconds: targetDuration ?? undefined,
          caption_bg_color: captionBgColor,
          caption_highlight_style: highlightStyle,
          background_music: backgroundMusic ?? undefined,
          background_music_start: backgroundMusic ? musicStart : undefined,
          background_music_end: backgroundMusic ? musicEnd : undefined,
          background_music_volume: backgroundMusic ? musicVolume : undefined,
          narration_volume: narrationVolume,
          text_overlays: textOverlays,
          caption_x: captionX,
          caption_y: captionY,
          image_adjustments: imageAdjustments,
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

  const captionPreview: CaptionPreview | undefined = imageUrl
    ? {
        x: captionX,
        y: captionY,
        text: text.trim() ? text.trim().slice(0, 40) : 'Así se ven tus subtítulos',
        bgColor: captionBgColor,
        highlightStyle,
      }
    : undefined

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
              captionPreview={captionPreview}
              onCaptionMove={(x, y) => {
                setCaptionX(x)
                setCaptionY(y)
              }}
              imageAdjustment={imageAdjustments[activeImageIndex]}
              onImagePan={(offsetX, offsetY) =>
                setImageAdjustments((prev) =>
                  prev.map((a, i) => (i === activeImageIndex ? { ...a, offset_x: offsetX, offset_y: offsetY } : a)),
                )
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
          imageFiles={imageFiles}
          onImageFilesAdded={(files) => {
            setImageFiles((prev) => [...prev, ...files])
            setImageAdjustments((prev) => [...prev, ...files.map(() => makeImageAdjustment())])
          }}
          onImageRemoveAt={(index) => {
            setImageFiles((prev) => prev.filter((_, i) => i !== index))
            setImageAdjustments((prev) => prev.filter((_, i) => i !== index))
            setActiveImageIndex((prev) => {
              if (prev === index) return 0
              return prev > index ? prev - 1 : prev
            })
          }}
          activeImageIndex={activeImageIndex}
          onSelectActiveImage={setActiveImageIndex}
          imageAdjustments={imageAdjustments}
          onImageZoomChange={(zoom) =>
            setImageAdjustments((prev) => prev.map((a, i) => (i === activeImageIndex ? { ...a, zoom } : a)))
          }
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
        narrationVolume={narrationVolume}
        onNarrationVolumeChange={setNarrationVolume}
        hasMusic={backgroundMusic !== null}
        musicPreviewUrl={musicPreviewUrl}
        musicKey={backgroundMusic}
        onMusicClick={() => setActiveTool('music')}
        onRangeChange={(start, end) => {
          setMusicStart(start)
          setMusicEnd(end)
        }}
        musicVolume={musicVolume}
        onMusicVolumeChange={setMusicVolume}
      />
    </form>
  )
}
