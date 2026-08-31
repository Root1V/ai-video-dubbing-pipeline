import { ImagePanel } from './panels/ImagePanel'
import { TextPanel } from './panels/TextPanel'
import { NarrationPanel } from './panels/NarrationPanel'
import { VoicePanel } from './panels/VoicePanel'
import { MusicPanel } from './panels/MusicPanel'
import { SubtitlesPanel } from './panels/SubtitlesPanel'
import type { EditorTool } from './types'
import type { CaptionHighlightStyle, TextOverlay, TtsVoiceOption } from '../../types/project'
import type { MusicTrack } from '../../types/musicTracks'

interface EditorRightPanelProps {
  activeTool: EditorTool
  isSubmitting: boolean

  imageFiles: File[]
  onImageFilesAdded: (files: File[]) => void
  onImageRemoveAt: (index: number) => void

  hasImage: boolean
  overlays: TextOverlay[]
  selectedOverlayId: string | null
  onAddOverlay: () => void
  onChangeOverlay: (overlay: TextOverlay) => void
  onRemoveOverlay: (id: string) => void

  text: string
  onTextChange: (text: string) => void
  targetLang: string
  onTargetLangChange: (lang: string) => void
  targetDuration: number | null
  onTargetDurationChange: (duration: number | null) => void

  voiceOption: TtsVoiceOption
  onVoiceOptionChange: (option: TtsVoiceOption) => void
  voiceFile: File | null
  onVoiceFileSelected: (file: File) => void
  onRemoveVoiceFile: () => void

  musicTracks: MusicTrack[]
  backgroundMusic: string | null
  onSelectMusic: (id: string | null) => void

  highlightStyle: CaptionHighlightStyle
  onHighlightStyleChange: (style: CaptionHighlightStyle) => void
  captionBgColor: string
  onCaptionBgColorChange: (color: string) => void
}

const TOOL_TITLES: Record<EditorTool, string> = {
  image: 'Imagen',
  text: 'Texto',
  narration: 'Narración',
  voice: 'Voz',
  music: 'Música de fondo',
  subtitles: 'Subtítulos',
}

/** Panel derecho del editor: muestra las opciones de la herramienta activa
 * (ver EditorLeftToolbar). Cada seccion es el mismo JSX/logica que antes
 * vivia apilado en un unico formulario largo -- aca solo cambia donde se
 * renderiza cada uno. */
export function EditorRightPanel(props: EditorRightPanelProps) {
  return (
    <aside className="flex w-[340px] shrink-0 flex-col gap-4 overflow-y-auto border-l border-border bg-card p-4">
      <h2 className="text-sm font-semibold text-muted-foreground">{TOOL_TITLES[props.activeTool]}</h2>

      {props.activeTool === 'image' && (
        <ImagePanel
          imageFiles={props.imageFiles}
          onFilesAdded={props.onImageFilesAdded}
          onRemoveAt={props.onImageRemoveAt}
          isSubmitting={props.isSubmitting}
        />
      )}

      {props.activeTool === 'text' && (
        <TextPanel
          hasImage={props.hasImage}
          overlays={props.overlays}
          selectedOverlayId={props.selectedOverlayId}
          onAddOverlay={props.onAddOverlay}
          onChangeOverlay={props.onChangeOverlay}
          onRemoveOverlay={props.onRemoveOverlay}
        />
      )}

      {props.activeTool === 'narration' && (
        <NarrationPanel
          text={props.text}
          onTextChange={props.onTextChange}
          targetLang={props.targetLang}
          onTargetLangChange={props.onTargetLangChange}
          targetDuration={props.targetDuration}
          onTargetDurationChange={props.onTargetDurationChange}
        />
      )}

      {props.activeTool === 'voice' && (
        <VoicePanel
          voiceOption={props.voiceOption}
          onVoiceOptionChange={props.onVoiceOptionChange}
          voiceFile={props.voiceFile}
          onVoiceFileSelected={props.onVoiceFileSelected}
          onRemoveVoiceFile={props.onRemoveVoiceFile}
          isSubmitting={props.isSubmitting}
        />
      )}

      {props.activeTool === 'music' && (
        <MusicPanel
          musicTracks={props.musicTracks}
          backgroundMusic={props.backgroundMusic}
          onSelectMusic={props.onSelectMusic}
        />
      )}

      {props.activeTool === 'subtitles' && (
        <SubtitlesPanel
          highlightStyle={props.highlightStyle}
          onHighlightStyleChange={props.onHighlightStyleChange}
          captionBgColor={props.captionBgColor}
          onCaptionBgColorChange={props.onCaptionBgColorChange}
        />
      )}
    </aside>
  )
}
