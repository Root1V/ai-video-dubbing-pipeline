import { MediaPanel } from './panels/MediaPanel'
import { TextPanel } from './panels/TextPanel'
import { EmojiPanel } from './panels/EmojiPanel'
import { NarrationPanel } from './panels/NarrationPanel'
import { VoicePanel } from './panels/VoicePanel'
import { MusicPanel } from './panels/MusicPanel'
import { SubtitlesPanel } from './panels/SubtitlesPanel'
import type { EditorTool } from './types'
import type {
  CaptionHighlightStyle,
  EmojiOverlay,
  MediaAdjustment,
  TextOverlay,
  TtsVoiceOption,
} from '../../types/project'
import type { MusicTrack } from '../../types/musicTracks'

interface EditorRightPanelProps {
  activeTool: EditorTool
  isSubmitting: boolean

  mediaFiles: File[]
  onMediaFilesAdded: (files: File[]) => void
  onMediaRemoveAt: (index: number) => void
  activeMediaIndex: number
  onSelectActiveMedia: (index: number) => void
  mediaAdjustments: MediaAdjustment[]
  onMediaZoomChange: (zoom: number) => void
  onMediaFilterPresetChange: (preset: MediaAdjustment['filter_preset']) => void
  onMediaReorder: (fromIndex: number, toIndex: number) => void

  hasImage: boolean
  overlays: TextOverlay[]
  selectedOverlayId: string | null
  onAddOverlay: () => void
  onChangeOverlay: (overlay: TextOverlay) => void
  onRemoveOverlay: (id: string) => void

  emojiOverlays: EmojiOverlay[]
  selectedEmojiOverlayId: string | null
  onAddEmojiOverlay: (emojiId: string) => void
  onChangeEmojiOverlay: (overlay: EmojiOverlay) => void
  onRemoveEmojiOverlay: (id: string) => void

  text: string
  onTextChange: (text: string) => void
  targetLang: string
  onTargetLangChange: (lang: string) => void
  targetDuration: number | null
  onTargetDurationChange: (duration: number | null) => void
  narrationVolume: number
  onNarrationVolumeChange: (volume: number) => void

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
  captionTextColor: string
  onCaptionTextColorChange: (color: string) => void
}

const TOOL_TITLES: Record<EditorTool, string> = {
  media: 'Imagen o video',
  text: 'Texto',
  emoji: 'Emoji',
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

      {props.activeTool === 'media' && (
        <MediaPanel
          mediaFiles={props.mediaFiles}
          onFilesAdded={props.onMediaFilesAdded}
          onRemoveAt={props.onMediaRemoveAt}
          isSubmitting={props.isSubmitting}
          activeIndex={props.activeMediaIndex}
          onSelectActive={props.onSelectActiveMedia}
          mediaAdjustments={props.mediaAdjustments}
          onZoomChange={props.onMediaZoomChange}
          onFilterPresetChange={props.onMediaFilterPresetChange}
          onReorder={props.onMediaReorder}
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

      {props.activeTool === 'emoji' && (
        <EmojiPanel
          hasImage={props.hasImage}
          overlays={props.emojiOverlays}
          selectedOverlayId={props.selectedEmojiOverlayId}
          onAddOverlay={props.onAddEmojiOverlay}
          onChangeOverlay={props.onChangeEmojiOverlay}
          onRemoveOverlay={props.onRemoveEmojiOverlay}
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
          narrationVolume={props.narrationVolume}
          onNarrationVolumeChange={props.onNarrationVolumeChange}
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
          captionTextColor={props.captionTextColor}
          onCaptionTextColorChange={props.onCaptionTextColorChange}
        />
      )}
    </aside>
  )
}
