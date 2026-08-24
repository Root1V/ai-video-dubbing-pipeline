interface VideoPreviewProps {
  src: string
}

export function VideoPreview({ src }: VideoPreviewProps) {
  return (
    <video controls preload="metadata" className="w-full rounded-xl border border-border bg-black" src={src}>
      Tu navegador no soporta la reproducción de video.
    </video>
  )
}
