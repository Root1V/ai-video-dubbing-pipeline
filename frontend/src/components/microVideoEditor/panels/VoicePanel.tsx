import { useDropzone } from 'react-dropzone'
import { FileAudio, UploadCloud, X } from 'lucide-react'
import { fetchVoiceSampleUrl } from '../../../api/samples'
import { SamplePreviewButton } from '../../media/SamplePreviewButton'
import { SelectableCard } from '../../ui/SelectableCard'
import { Button } from '../../ui/Button'
import { cn } from '../../../lib/cn'
import { formatBytes } from '../../../lib/format'
import type { TtsVoiceOption } from '../../../types/project'

const VOICE_OPTIONS: { value: TtsVoiceOption; label: string; description: string }[] = [
  { value: 'public_female', label: 'Locutora', description: 'Voz pública femenina (por defecto)' },
  { value: 'public_male', label: 'Locutor', description: 'Voz pública masculina' },
  { value: 'own', label: 'Mi voz', description: 'Sube tu propia muestra de voz' },
]

interface VoicePanelProps {
  voiceOption: TtsVoiceOption
  onVoiceOptionChange: (option: TtsVoiceOption) => void
  voiceFile: File | null
  onVoiceFileSelected: (file: File) => void
  onRemoveVoiceFile: () => void
  isSubmitting: boolean
}

export function VoicePanel({
  voiceOption,
  onVoiceOptionChange,
  voiceFile,
  onVoiceFileSelected,
  onRemoveVoiceFile,
  isSubmitting,
}: VoicePanelProps) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'audio/*': [] },
    multiple: false,
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0]
      if (selected) onVoiceFileSelected(selected)
    },
  })

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-col gap-2">
        {VOICE_OPTIONS.map((option) => (
          <SelectableCard
            key={option.value}
            selected={voiceOption === option.value}
            onSelect={() => onVoiceOptionChange(option.value)}
          >
            <div className="flex w-full items-center justify-between gap-2">
              <span className="text-sm font-medium">{option.label}</span>
              {option.value !== 'own' && (
                <SamplePreviewButton
                  sampleKey={`voice-${option.value}`}
                  fetchUrl={() => fetchVoiceSampleUrl(option.value)}
                />
              )}
            </div>
            <span className="text-xs text-muted-foreground">{option.description}</span>
          </SelectableCard>
        ))}
      </div>

      {voiceOption === 'own' &&
        (!voiceFile ? (
          <div
            {...getRootProps()}
            className={cn(
              'mt-2 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-8 text-center transition-colors',
              isDragActive && 'border-primary bg-primary/5',
            )}
          >
            <input {...getInputProps()} />
            <UploadCloud className="h-5 w-5 text-primary" />
            <p className="text-sm text-muted-foreground">
              Arrastra un .wav/.mp3 aquí o haz clic para seleccionarlo (6-15s de la voz a clonar)
            </p>
          </div>
        ) : (
          <div className="mt-2 flex items-center gap-3 rounded-xl border border-border p-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <FileAudio className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{voiceFile.name}</p>
              <p className="text-sm text-muted-foreground">{formatBytes(voiceFile.size)}</p>
            </div>
            <SamplePreviewButton
              key={`${voiceFile.name}-${voiceFile.size}`}
              sampleKey="voice-own"
              fetchUrl={() => Promise.resolve(URL.createObjectURL(voiceFile))}
            />
            {!isSubmitting && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onRemoveVoiceFile}
                aria-label="Quitar voz de referencia"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        ))}
    </div>
  )
}
