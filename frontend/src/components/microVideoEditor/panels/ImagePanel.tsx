import { useDropzone } from 'react-dropzone'
import { Image as ImageIcon, UploadCloud, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import { cn } from '../../../lib/cn'
import { formatBytes } from '../../../lib/format'

interface ImagePanelProps {
  imageFile: File | null
  onFileSelected: (file: File) => void
  onRemove: () => void
  isSubmitting: boolean
}

export function ImagePanel({ imageFile, onFileSelected, onRemove, isSubmitting }: ImagePanelProps) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'image/*': [] },
    multiple: false,
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0]
      if (selected) onFileSelected(selected)
    },
  })

  return (
    <div className="flex flex-col gap-1.5">
      {!imageFile ? (
        <div
          {...getRootProps()}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-8 text-center transition-colors',
            isDragActive && 'border-primary bg-primary/5',
          )}
        >
          <input {...getInputProps()} />
          <UploadCloud className="h-5 w-5 text-primary" />
          <p className="text-sm text-muted-foreground">Arrastra una imagen aquí o haz clic para seleccionarla</p>
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
            <Button type="button" variant="ghost" size="icon" onClick={onRemove} aria-label="Quitar imagen">
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
