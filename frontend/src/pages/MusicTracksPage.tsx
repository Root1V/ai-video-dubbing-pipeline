import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { Music, Trash2, UploadCloud } from 'lucide-react'
import { createMusicTrack, deleteMusicTrack, fetchMusicTracks } from '../api/musicTracks'
import { fetchMusicSampleUrl } from '../api/samples'
import { SamplePreviewButton } from '../components/media/SamplePreviewButton'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { cn } from '../lib/cn'
import { getErrorMessage } from '../lib/errors'
import { MUSIC_CATEGORY_LABELS } from '../lib/labels'
import type { MusicCategory } from '../types/musicTracks'

const CATEGORIES = Object.keys(MUSIC_CATEGORY_LABELS) as MusicCategory[]

export function MusicTracksPage() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<MusicCategory>('energy_pop')
  const [file, setFile] = useState<File | null>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'audio/*': [] },
    multiple: false,
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0]
      if (selected) setFile(selected)
    },
  })

  const { data: tracks = [], isLoading } = useQuery({
    queryKey: ['music-tracks'],
    queryFn: () => fetchMusicTracks(),
  })

  const createMutation = useMutation({
    mutationFn: createMusicTrack,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['music-tracks'] })
      setTitle('')
      setFile(null)
    },
    onError: (err) => setError(getErrorMessage(err, 'No se pudo agregar la pista.')),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteMusicTrack,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['music-tracks'] })
    },
    onError: (err) => setError(getErrorMessage(err, 'No se pudo borrar la pista.')),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!title.trim() || !file) {
      setError('Ingresa un título y selecciona un archivo de audio.')
      return
    }
    setError(null)
    createMutation.mutate({ title: title.trim(), category, file })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Música de fondo</h1>
        <p className="text-sm text-muted-foreground">
          Agrega pistas al catálogo por categoría. Al subir un archivo se recorta el silencio inicial
          y se convierte a WAV automáticamente antes de guardarlo.
        </p>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="track-title" className="text-sm font-medium">
                  Título
                </label>
                <Input
                  id="track-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Nombre de la pista"
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="track-category" className="text-sm font-medium">
                  Categoría
                </label>
                <Select
                  id="track-category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as MusicCategory)}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {MUSIC_CATEGORY_LABELS[c]}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            {!file ? (
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
                  Arrastra un archivo de audio aquí o haz clic para seleccionarlo
                </p>
              </div>
            ) : (
              <div className="flex items-center gap-4 rounded-xl border border-border p-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Music className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{file.name}</p>
                </div>
                <Button type="button" variant="ghost" size="sm" onClick={() => setFile(null)}>
                  Quitar
                </Button>
              </div>
            )}

            <div className="flex justify-end">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Procesando…' : 'Agregar pista'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <div className="flex flex-col gap-4">
          {CATEGORIES.map((c) => {
            const categoryTracks = tracks.filter((t) => t.category === c)
            return (
              <Card key={c}>
                <CardContent className="flex flex-col gap-3 p-6">
                  <h2 className="text-sm font-semibold">{MUSIC_CATEGORY_LABELS[c]}</h2>
                  {categoryTracks.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Sin pistas todavía.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {categoryTracks.map((track) => (
                        <div
                          key={track.id}
                          className="flex items-center justify-between gap-2 rounded-xl border border-border p-3"
                        >
                          <span className="text-sm font-medium">{track.title}</span>
                          <div className="flex items-center gap-2">
                            <SamplePreviewButton
                              sampleKey={`music-${track.id}`}
                              fetchUrl={() => fetchMusicSampleUrl(track.id)}
                            />
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              aria-label="Borrar pista"
                              disabled={deleteMutation.isPending}
                              onClick={() => deleteMutation.mutate(track.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
