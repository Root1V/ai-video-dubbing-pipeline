import { useEffect, useState } from 'react'
import type { DragEvent } from 'react'
import { useDropzone } from 'react-dropzone'
import { GripVertical, UploadCloud, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import { cn } from '../../../lib/cn'
import { formatBytes } from '../../../lib/format'
import type { FilterPreset, ImageAdjustment } from '../../../types/project'

const FILTER_PRESET_OPTIONS: { value: FilterPreset; label: string }[] = [
  { value: 'none', label: 'Original' },
  { value: 'sepia', label: 'Sepia' },
  { value: 'bw', label: 'B&N' },
  { value: 'cool', label: 'Frío' },
  { value: 'warm', label: 'Cálido' },
  { value: 'dramatic', label: 'Dramático' },
]

interface ImagePanelProps {
  imageFiles: File[]
  onFilesAdded: (files: File[]) => void
  onRemoveAt: (index: number) => void
  isSubmitting: boolean
  /** Indice de la imagen actualmente activa en el lienzo para ajustar su
   * encuadre (pan/zoom, ver RM-30) y su filtro de color (ver RM-31). */
  activeIndex: number
  onSelectActive: (index: number) => void
  imageAdjustments: ImageAdjustment[]
  onZoomChange: (zoom: number) => void
  onFilterPresetChange: (preset: FilterPreset) => void
  /** Reordena las imagenes (arrastrando desde el icono de agarre) -- el
   * orden del array es el orden en que aparecen en el video final (ver
   * RM-29). */
  onReorder: (fromIndex: number, toIndex: number) => void
}

/** Con mas de una imagen (ver RM-29), el video las recorre EN ESTE ORDEN --
 * cada fila numerada de aca abajo es un tramo del video, no solo una lista
 * de archivos subidos: arrastra desde el icono de agarre para reordenarlas.
 * Cada fila es clickeable (fuera del icono de agarre) para elegirla como la
 * imagen activa en el lienzo (ver RM-30, ajuste de encuadre): arrastrala en
 * el lienzo para reposicionarla, o usa la barra de Zoom/Filtro de aca abajo,
 * que siempre refleja la imagen activa. */
export function ImagePanel({
  imageFiles,
  onFilesAdded,
  onRemoveAt,
  isSubmitting,
  activeIndex,
  onSelectActive,
  imageAdjustments,
  onZoomChange,
  onFilterPresetChange,
  onReorder,
}: ImagePanelProps) {
  const [thumbnails, setThumbnails] = useState<string[]>([])
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)

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

  function handleRowDrop(event: DragEvent<HTMLDivElement>, index: number) {
    event.preventDefault()
    if (draggedIndex !== null && draggedIndex !== index) onReorder(draggedIndex, index)
    setDraggedIndex(null)
  }

  const activeAdjustment = imageAdjustments[activeIndex]

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
            <div
              key={`${file.name}-${file.size}-${index}`}
              onClick={() => onSelectActive(index)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => handleRowDrop(event, index)}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-xl border p-2 transition-colors',
                index === activeIndex ? 'border-primary bg-primary/5' : 'border-border',
                draggedIndex === index && 'opacity-50',
              )}
            >
              <span
                draggable={!isSubmitting}
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = 'move'
                  setDraggedIndex(index)
                }}
                onClick={(event) => event.stopPropagation()}
                className="cursor-grab text-muted-foreground active:cursor-grabbing"
                aria-label={`Arrastrar para reordenar la imagen ${index + 1}`}
              >
                <GripVertical className="h-4 w-4" />
              </span>
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
          ))}
          {imageFiles.length > 1 && (
            <p className="text-xs text-muted-foreground">
              El video recorre las imágenes en este orden, repartiendo la duración total entre todas.
            </p>
          )}
        </div>
      )}

      {activeAdjustment && (
        <div className="flex flex-col gap-2 rounded-xl border border-dashed border-border p-3">
          <span className="text-xs font-medium text-muted-foreground">
            Ajustando imagen {activeIndex + 1}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Zoom</span>
            <input
              type="range"
              min={1}
              max={2.5}
              step={0.05}
              value={activeAdjustment.zoom}
              onChange={(event) => onZoomChange(Number(event.target.value))}
              disabled={isSubmitting}
              className="flex-1 accent-primary"
              aria-label={`Zoom de la imagen ${activeIndex + 1}`}
            />
            <span className="w-10 text-right text-xs text-muted-foreground">
              {activeAdjustment.zoom.toFixed(2)}x
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {FILTER_PRESET_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onFilterPresetChange(option.value)}
                disabled={isSubmitting}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs transition-colors',
                  activeAdjustment.filter_preset === option.value
                    ? 'border-primary bg-primary/5 font-medium'
                    : 'border-border hover:bg-secondary/50',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
