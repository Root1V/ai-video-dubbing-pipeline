import { Fragment, useEffect, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { UploadCloud, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import { cn } from '../../../lib/cn'
import { formatBytes } from '../../../lib/format'
import type { ImageAdjustment } from '../../../types/project'

interface ImagePanelProps {
  imageFiles: File[]
  onFilesAdded: (files: File[]) => void
  onRemoveAt: (index: number) => void
  isSubmitting: boolean
  /** Indice de la imagen actualmente activa en el lienzo para ajustar su
   * encuadre (pan/zoom, ver RM-30). */
  activeIndex: number
  onSelectActive: (index: number) => void
  imageAdjustments: ImageAdjustment[]
  onZoomChange: (zoom: number) => void
}

/** Con mas de una imagen (ver RM-29), el video las recorre EN ESTE ORDEN --
 * cada fila numerada de aca abajo es un tramo del video, no solo una lista
 * de archivos subidos. Cada fila es clickeable para elegirla como la imagen
 * activa en el lienzo (ver RM-30, ajuste de encuadre): arrastrala en el
 * lienzo para reposicionarla, o usa el control de zoom que aparece aca
 * debajo de la fila activa. */
export function ImagePanel({
  imageFiles,
  onFilesAdded,
  onRemoveAt,
  isSubmitting,
  activeIndex,
  onSelectActive,
  imageAdjustments,
  onZoomChange,
}: ImagePanelProps) {
  const [thumbnails, setThumbnails] = useState<string[]>([])

  useEffect(() => {
    const urls = imageFiles.map((f) => URL.createObjectURL(f))
    setThumbnails(urls)
    return () => urls.forEach((u) => URL.revokeObjectURL(u))
  }, [imageFiles])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'image/*': [] },
    multiple: true,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) onFilesAdded(acceptedFiles)
    },
  })

  return (
    <div className="flex flex-col gap-3">
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
          {imageFiles.length === 0
            ? 'Arrastra una o más imágenes aquí o haz clic para seleccionarlas'
            : 'Agregar más imágenes'}
        </p>
      </div>

      {imageFiles.length > 0 && (
        <div className="flex flex-col gap-2">
          {imageFiles.map((file, index) => (
            <Fragment key={`${file.name}-${file.size}-${index}`}>
              <div
                onClick={() => onSelectActive(index)}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-xl border p-2 transition-colors',
                  index === activeIndex ? 'border-primary bg-primary/5' : 'border-border',
                )}
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                  {index + 1}
                </span>
                {thumbnails[index] && (
                  <img
                    src={thumbnails[index]}
                    alt=""
                    className="h-11 w-11 shrink-0 rounded-lg object-cover"
                  />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
                </div>
                {!isSubmitting && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={(event) => {
                      event.stopPropagation()
                      onRemoveAt(index)
                    }}
                    aria-label={`Quitar imagen ${index + 1}`}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              {index === activeIndex && imageAdjustments[index] && (
                <div className="flex items-center gap-2 rounded-xl border border-dashed border-border px-3 py-2">
                  <span className="text-xs text-muted-foreground">Zoom</span>
                  <input
                    type="range"
                    min={1}
                    max={2.5}
                    step={0.05}
                    value={imageAdjustments[index].zoom}
                    onChange={(event) => onZoomChange(Number(event.target.value))}
                    disabled={isSubmitting}
                    className="flex-1 accent-primary"
                    aria-label={`Zoom de la imagen ${index + 1}`}
                  />
                  <span className="w-10 text-right text-xs text-muted-foreground">
                    {imageAdjustments[index].zoom.toFixed(2)}x
                  </span>
                </div>
              )}
            </Fragment>
          ))}
          {imageFiles.length > 1 && (
            <p className="text-xs text-muted-foreground">
              El video recorre las imágenes en este orden, repartiendo la duración total entre todas.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
