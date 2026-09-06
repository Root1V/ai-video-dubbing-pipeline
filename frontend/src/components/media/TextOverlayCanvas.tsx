import type { CSSProperties, MouseEvent as ReactMouseEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import type {
  CaptionHighlightStyle,
  EmojiOverlay,
  FilterPreset,
  MediaAdjustment,
  TextOverlay,
} from '../../types/project'
import { cn } from '../../lib/cn'

// Aproximacion visual (no un match exacto de pixeles) de los presets de
// color de RM-31 -- el filtro real se aplica en ffmpeg al generar el video.
// 'dramatic' no tiene equivalente nativo de vinieta en CSS `filter`, se
// aproxima por separado con un overlay radial (ver DRAMATIC_VIGNETTE_STYLE).
const CSS_FILTER_BY_PRESET: Record<FilterPreset, string | undefined> = {
  none: undefined,
  sepia: 'sepia(0.8)',
  bw: 'grayscale(1)',
  cool: 'hue-rotate(180deg) saturate(1.1)',
  warm: 'sepia(0.3) saturate(1.3) hue-rotate(-10deg)',
  dramatic: 'contrast(1.15) saturate(1.2)',
}

// Los valores de Outline/Shadow que usa el backend (ver
// _text_style_ass_params en generate_micro_video.py) estan en pixeles sobre
// un lienzo de 1080 de ancho -- misma escala que overlay.font_size (ver
// `fontSize` mas abajo). Convertirlos a la MISMA unidad `cqw` que el
// tamano de fuente es lo que hace que el grosor del contorno/sombra en el
// preview escale igual que el font-size (antes eran px fijos: un font_size
// grande dejaba el contorno desproporcionadamente fino, y viceversa).
function px2cqw(px: number): string {
  return `${(px / 1080) * 100}cqw`
}

// Aproximacion visual (no pixel-perfect) de los estilos de texto de RM-33
// -- el resultado real lo arma el backend via tags ASS (Outline/Shadow, o
// un degradado por caracter con \1c, ver generate_micro_video.py). El
// degradado en particular puede verse INCLUSO mas suave aca que en el
// video final (CSS linear-gradient es continuo, el backend lo discretiza
// por caracter), mismo criterio ya aceptado para el resto de los previews
// de este editor.
function textOverlayStyle(overlay: TextOverlay): CSSProperties {
  switch (overlay.text_style) {
    case 'hard_shadow':
      return { color: overlay.color, textShadow: `${px2cqw(8)} ${px2cqw(8)} 0 rgba(0,0,0,0.9)` }
    case 'thick_outline':
      return {
        color: overlay.color,
        WebkitTextStroke: `${px2cqw(10)} black`,
        paintOrder: 'stroke fill',
      }
    case 'long_shadow':
      // Una sola copia de fondo desplazada, igual que el `Shadow` de ASS
      // (que tampoco es una "cinta" escalonada) -- pero encadenar varios
      // pasos intermedios (en vez de un solo salto de 18px) es lo que la
      // hace leerse como una sombra continua en vez de un texto duplicado
      // "flotando" al lado.
      return {
        color: overlay.color,
        textShadow: Array.from({ length: 18 }, (_, i) => `${px2cqw(i + 1)} ${px2cqw(i + 1)} 0 rgba(0,0,0,0.9)`).join(
          ', ',
        ),
      }
    case 'hollow':
      return {
        color: 'transparent',
        WebkitTextFillColor: 'transparent',
        WebkitTextStroke: `${px2cqw(6)} ${overlay.color}`,
        paintOrder: 'stroke fill',
      }
    case 'neon_glow':
      return {
        color: overlay.color,
        textShadow: `0 0 ${px2cqw(4)} ${overlay.accent_color}, 0 0 ${px2cqw(10)} ${overlay.accent_color}, 0 0 ${px2cqw(20)} ${overlay.accent_color}`,
      }
    case 'colored_outline':
      return {
        color: overlay.color,
        WebkitTextStroke: `${px2cqw(6)} ${overlay.accent_color}`,
        paintOrder: 'stroke fill',
      }
    case 'gradient':
      return {
        background: `linear-gradient(90deg, ${overlay.color}, ${overlay.accent_color})`,
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        color: 'transparent',
      }
    default:
      return { color: overlay.color, textShadow: '0 0 3px rgba(0,0,0,0.8)' }
  }
}

// Debe coincidir con el aspecto del contenedor (`aspectRatio: '9 / 16'` mas
// abajo) y con VIDEO_WIDTH/VIDEO_HEIGHT del backend.
const CONTAINER_ASPECT = 9 / 16

/** Cuanto mas grande es la imagen ya escalada (cover-fit + zoom, ver RM-30)
 * que el marco, como fraccion del ancho/alto del marco -- 0 = sin sobrante
 * en ese eje (no se puede desplazar). Mismo orden de operaciones que
 * `ffmpeg_processor.py::render_image_video`: 1) cubrir el marco 9:16
 * (aspect-fit "increase"), 2) escalar un extra `zoom`x. */
function computeExcess(naturalSize: { width: number; height: number } | null, zoom: number) {
  if (!naturalSize) return { excessX: 0, excessY: 0 }
  const imageAspect = naturalSize.width / naturalSize.height
  if (imageAspect >= CONTAINER_ASPECT) {
    return { excessX: (imageAspect / CONTAINER_ASPECT) * zoom - 1, excessY: zoom - 1 }
  }
  return { excessX: zoom - 1, excessY: (CONTAINER_ASPECT / imageAspect) * zoom - 1 }
}

export interface CaptionPreview {
  x: number
  y: number
  text: string
  bgColor: string
  /** Color del texto -- solo se usa en los estilos "background" y
   * "karaoke_background" (ver caption_text_color). */
  textColor: string
  highlightStyle: CaptionHighlightStyle
}

interface TextOverlayCanvasProps {
  mediaUrl: string
  /** 'video' cuando el item activo es un clip de video (ver RM-36) -- de lo
   * contrario se renderiza como imagen (comportamiento previo). */
  mediaKind?: 'image' | 'video'
  overlays: TextOverlay[]
  selectedId: string | null
  onSelect: (id: string) => void
  onMove: (id: string, x: number, y: number) => void
  /** Preview arrastrable de donde van a aparecer los captions de la
   * narracion -- mismo mecanismo de drag que un TextOverlay, pero es un
   * singleton (no forma parte de la lista de overlays). undefined = no
   * mostrar nada (p.ej. sin narracion todavia). */
  captionPreview?: CaptionPreview
  onCaptionMove?: (x: number, y: number) => void
  /** Encuadre (pan/zoom) del item de fondo actualmente activo (ver RM-30)
   * -- undefined = sin ajuste (recorte centrado, comportamiento previo).
   * `onMediaPan` habilita arrastrar el item para reposicionarlo. */
  mediaAdjustment?: MediaAdjustment
  onMediaPan?: (offsetX: number, offsetY: number) => void
  /** Solo si mediaKind es 'video' (ver RM-36): duracion real del clip,
   * sondeada al cargar su metadata -- usada por la franja de recorte. */
  onMediaDurationLoaded?: (duration: number) => void
  /** Solo si mediaKind es 'video' (ver RM-36): rango [clipStart, clipEnd)
   * elegido en VideoClipTrimTimeline -- el preview reproduce en loop DENTRO
   * de este rango (no el clip completo) y salta a el apenas cambia, para
   * que ajustar los limites se vea reflejado de inmediato. undefined en
   * clipEnd = hasta el final real del clip. */
  clipStart?: number
  clipEnd?: number
  /** Emojis superpuestos (ver RM-32) -- misma mecanica de drag que
   * TextOverlay. `emojiImageUrls` son las URLs ya resueltas (blob, via
   * fetchEmojiSampleUrl) por `emoji_id`, precargadas una sola vez para
   * todo el set curado -- un id sin URL todavia cargada simplemente no
   * se dibuja ese frame. */
  emojiOverlays?: EmojiOverlay[]
  emojiImageUrls?: Record<string, string>
  selectedEmojiId?: string | null
  onSelectEmoji?: (id: string) => void
  onMoveEmoji?: (id: string, x: number, y: number) => void
}

/** Lienzo de edicion: la imagen de fondo (misma relacion de aspecto 9:16
 * que el video final) con cada TextOverlay encima, arrastrable a mano con
 * eventos de puntero nativos -- no hay libreria de drag-and-drop instalada
 * y no hace falta agregar una solo para mover unas pocas cajas libres (ver
 * RM-28 en docs/roadmap.md). `x`/`y` de cada overlay son fracciones 0-1 del
 * ancho/alto, asi que la posicion no depende del tamano en pantalla. */
export function TextOverlayCanvas({
  mediaUrl,
  mediaKind = 'image',
  overlays,
  selectedId,
  onSelect,
  onMove,
  captionPreview,
  onCaptionMove,
  mediaAdjustment,
  onMediaPan,
  onMediaDurationLoaded,
  clipStart,
  clipEnd,
  emojiOverlays,
  emojiImageUrls,
  selectedEmojiId,
  onSelectEmoji,
  onMoveEmoji,
}: TextOverlayCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null)

  useEffect(() => {
    setNaturalSize(null)
    // Si el elemento (un blob: URL, sin red de por medio) ya esta decodificado
    // para cuando este efecto corre, el evento `load`/`loadedmetadata` nativo
    // puede haberse disparado antes de que React llegue a atar el handler de
    // mas abajo -- sin este chequeo, `naturalSize` queda en null para siempre
    // en ese caso. Confirmado en Safari: hace que el zoom/pan no tengan ningun
    // efecto, porque `backgroundMediaStyle` cae al fallback que los ignora
    // (ver mas abajo) cuando `naturalSize` es null.
    if (mediaKind === 'video') {
      const video = videoRef.current
      if (video && video.readyState >= 1 && video.videoWidth > 0) {
        setNaturalSize({ width: video.videoWidth, height: video.videoHeight })
      }
      return
    }
    const img = imgRef.current
    if (img && img.complete && img.naturalWidth > 0) {
      setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight })
    }
  }, [mediaUrl, mediaKind])

  // Salta el preview al nuevo limite apenas el usuario ajusta el recorte en
  // VideoClipTrimTimeline (ver RM-36) -- sin esto, ver el efecto de mover un
  // limite requeriria esperar a que la reproduccion en loop llegue ahi sola.
  // Si el FIN es lo unico que cambio, muestra el frame justo antes de el
  // (para previsualizar donde corta); en cualquier otro caso (cambio el
  // inicio, o es un clip nuevo) muestra el inicio del recorte -- el primer
  // frame de un clip recien cargado ya se sincroniza en onLoadedMetadata,
  // antes de que este efecto corra (metadata todavia no lista).
  const clipRangeRef = useRef<{ url: string; start: number } | null>(null)
  useEffect(() => {
    if (mediaKind !== 'video') {
      clipRangeRef.current = null
      return
    }
    const video = videoRef.current
    if (!video || video.readyState < 1) return
    const rangeStart = clipStart ?? 0
    const rangeEnd = clipEnd ?? video.duration
    const prev = clipRangeRef.current
    clipRangeRef.current = { url: mediaUrl, start: rangeStart }
    if (prev && prev.url === mediaUrl && rangeStart === prev.start) {
      video.currentTime = Math.max(rangeStart, rangeEnd - 0.05)
    } else {
      video.currentTime = rangeStart
    }
  }, [mediaUrl, mediaKind, clipStart, clipEnd])

  // Mouse events (no Pointer Events / setPointerCapture) a proposito: Safari
  // tiene un bug conocido y de larga data donde, tras `setPointerCapture`,
  // `pointermove`/`pointerup` dejan de dispararse en cuanto el cursor sale
  // del elemento capturado -- incluso con los listeners puestos en `window`
  // (ver https://github.com/w3c/pointerevents/issues/407) -- lo que rompia
  // por completo arrastrar overlays/imagen en Safari. Mouse events puros no
  // tienen ese problema y son mas que suficientes: esta interaccion es de
  // escritorio (mouse), no necesita soporte multi-touch.
  function handlePointerDown(
    event: ReactMouseEvent<HTMLElement>,
    onDrag: (x: number, y: number) => void,
  ) {
    event.preventDefault()
    const container = containerRef.current
    if (!container) return

    function handleMouseMove(moveEvent: MouseEvent) {
      if (!container) return
      const rect = container.getBoundingClientRect()
      const x = Math.min(1, Math.max(0, (moveEvent.clientX - rect.left) / rect.width))
      const y = Math.min(1, Math.max(0, (moveEvent.clientY - rect.top) / rect.height))
      onDrag(x, y)
    }

    function handleMouseUp() {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  // A diferencia de handlePointerDown (mapea la posicion ABSOLUTA del
  // puntero, natural para "donde soltaste el texto"), reposicionar una
  // imagen se siente como arrastrar una foto: el contenido debe seguir al
  // cursor. Se acumula el DELTA de movimiento y se resta del offset actual
  // -- arrastrar hacia la derecha revela mas del lado izquierdo de la
  // imagen, igual que un editor de recorte de foto estandar.
  // Mouse events, mismo motivo que handlePointerDown de arriba (bug de
  // Safari con setPointerCapture).
  function handleMediaPointerDown(event: ReactMouseEvent<HTMLElement>) {
    const pan = onMediaPan
    if (!pan || !mediaAdjustment) return
    event.preventDefault()
    const container = containerRef.current
    if (!container) return
    let lastX = event.clientX
    let lastY = event.clientY
    let offsetX = mediaAdjustment.offset_x
    let offsetY = mediaAdjustment.offset_y
    // El sobrante (cuanto mas grande es la imagen/clip ya escalado que el
    // marco) se calcula UNA vez al empezar a arrastrar -- no cambia durante
    // el gesto (zoom no cambia mientras se arrastra). Dividir por el
    // sobrante en PIXELES (no por el ancho del contenedor) es lo que hace
    // que el arrastre siga al cursor 1 a 1 -- si un eje no tiene sobrante
    // (p.ej. recien al hacer zoom aparece sobrante vertical que antes era
    // cero), antes se quedaba trabado sin poder moverse en ese eje.
    const { excessX, excessY } = computeExcess(naturalSize, mediaAdjustment.zoom)

    function handleMouseMove(moveEvent: MouseEvent) {
      if (!container) return
      const rect = container.getBoundingClientRect()
      const dx = moveEvent.clientX - lastX
      const dy = moveEvent.clientY - lastY
      if (excessX > 0.001) offsetX = Math.min(1, Math.max(0, offsetX - dx / (excessX * rect.width)))
      if (excessY > 0.001) offsetY = Math.min(1, Math.max(0, offsetY - dy / (excessY * rect.height)))
      lastX = moveEvent.clientX
      lastY = moveEvent.clientY
      pan?.(offsetX, offsetY)
    }

    function handleMouseUp() {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  // Reproduce a mano el mismo orden de operaciones que
  // `ffmpeg_processor.py::render_image_video` (cubrir el marco, escalar por
  // `zoom`, recortar segun offset_x/offset_y) -- a diferencia de
  // `object-position` + `transform:scale` por separado, esto SI le agrega
  // sobrante real a cada eje al hacer zoom (ver `computeExcess`), asi que
  // el arrastre funciona en cualquier direccion una vez zoomeado, no solo
  // en el eje que ya tenia sobrante por la relacion de aspecto original.
  function backgroundMediaStyle(): CSSProperties | undefined {
    if (!mediaAdjustment) return undefined
    const { offset_x: offsetX, offset_y: offsetY, zoom, filter_preset: filterPreset } = mediaAdjustment
    if (!naturalSize) {
      // Mientras se carga la imagen y no conocemos su tamano natural: misma
      // aproximacion simple de antes, para no saltar visualmente apenas carga.
      return {
        objectFit: 'cover',
        objectPosition: `${offsetX * 100}% ${offsetY * 100}%`,
        filter: CSS_FILTER_BY_PRESET[filterPreset],
      }
    }
    const { excessX, excessY } = computeExcess(naturalSize, zoom)
    return {
      position: 'absolute',
      // El preflight de Tailwind pone `img { max-width: 100%; height: auto }`
      // -- sin anular eso aca, el ancho/alto de abajo queda capado a 100%
      // sin importar el zoom, y el pan se ve "trabado" (bug reportado).
      maxWidth: 'none',
      maxHeight: 'none',
      width: `${(1 + excessX) * 100}%`,
      height: `${(1 + excessY) * 100}%`,
      left: `${-excessX * offsetX * 100}%`,
      top: `${-excessY * offsetY * 100}%`,
      objectFit: 'cover',
      filter: CSS_FILTER_BY_PRESET[filterPreset],
    }
  }

  return (
    <div
      ref={containerRef}
      className="relative mx-auto h-full max-h-full max-w-full select-none overflow-hidden rounded-2xl border border-border bg-secondary/30 shadow-lg"
      style={{ aspectRatio: '9 / 16', containerType: 'inline-size' }}
    >
      {mediaKind === 'video' ? (
        <video
          ref={videoRef}
          src={mediaUrl}
          playsInline
          // Mismo criterio que el `<img>` de abajo: `cursor-grab`, no
          // `cursor-move` (sin glyph nativo en macOS); mousedown en mouse
          // events puros (bug de Safari con setPointerCapture, ver arriba).
          className={cn(
            'h-full w-full object-cover',
            onMediaPan && 'cursor-grab active:cursor-grabbing',
          )}
          draggable={false}
          onMouseDown={onMediaPan ? handleMediaPointerDown : undefined}
          onLoadedMetadata={(event) => {
            const video = event.currentTarget
            setNaturalSize({ width: video.videoWidth, height: video.videoHeight })
            onMediaDurationLoaded?.(video.duration)
            video.currentTime = clipStart ?? 0
            // CON sonido a proposito (sin atributo `muted`/`autoPlay`, se
            // dispara a mano aca): el usuario necesita ESCUCHAR el clip
            // para elegir bien donde recortarlo (ver RM-36). `muted` se
            // resetea a false en cada clip nuevo -- el elemento <video> se
            // reusa entre items (mismo nodo, solo cambia `src`), asi que un
            // fallback mudo de un clip anterior no debe pegarsele al
            // siguiente. Si el navegador bloquea el autoplay con audio
            // (falta un gesto previo del usuario en esta pestaña), se
            // reintenta mudo -- que al menos siga reproduciendo, aunque sin
            // sonido en ese caso.
            video.muted = false
            video.play().catch(() => {
              video.muted = true
              void video.play().catch(() => {})
            })
          }}
          // Sin el atributo nativo `loop`: reinicia siempre en 0, no en
          // clipStart -- el loop dentro del rango elegido se hace a mano
          // aca, reiniciando en clipStart apenas se alcanza clipEnd.
          onTimeUpdate={(event) => {
            const video = event.currentTarget
            const rangeEnd = clipEnd ?? video.duration
            if (video.currentTime >= rangeEnd - 0.02) {
              video.currentTime = clipStart ?? 0
            }
          }}
          style={backgroundMediaStyle()}
        />
      ) : (
        <img
          ref={imgRef}
          src={mediaUrl}
          alt=""
          // `draggable={false}` (el atributo HTML) no alcanza en Safari: sigue
          // iniciando su propio gesto nativo de "arrastrar la imagen como
          // archivo" en vez de dispararnos mousedown/mousemove normales, salvo
          // que ademas se le apague `-webkit-user-drag` por CSS.
          // `cursor-grab`, no `cursor-move`: macOS no tiene un glyph nativo
          // para el cursor "move" y Safari cae al de flecha normal en vez de
          // dibujar algo generico -- "grab" (mano abierta) si tiene glyph
          // propio en macOS y se ve bien en los tres navegadores.
          className={cn(
            'h-full w-full object-cover [-webkit-user-drag:none]',
            onMediaPan && 'cursor-grab active:cursor-grabbing',
          )}
          draggable={false}
          onMouseDown={onMediaPan ? handleMediaPointerDown : undefined}
          onLoad={(event) =>
            setNaturalSize({
              width: event.currentTarget.naturalWidth,
              height: event.currentTarget.naturalHeight,
            })
          }
          style={backgroundMediaStyle()}
        />
      )}
      {mediaAdjustment?.filter_preset === 'dramatic' && (
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.55) 100%)' }}
        />
      )}
      {overlays.map((overlay) => (
        <div
          key={overlay.id}
          onMouseDown={(event) => {
            onSelect(overlay.id)
            handlePointerDown(event, (x, y) => onMove(overlay.id, x, y))
          }}
          className={cn(
            'absolute max-w-[90%] -translate-x-1/2 -translate-y-1/2 cursor-grab active:cursor-grabbing whitespace-pre-wrap px-1 text-center',
            overlay.id === selectedId && 'outline outline-2 outline-dashed outline-primary',
          )}
          style={{
            left: `${overlay.x * 100}%`,
            top: `${overlay.y * 100}%`,
            fontFamily: overlay.font_family,
            fontWeight: overlay.bold ? 'bold' : 'normal',
            // El tamano de fuente en el video final esta en px sobre un
            // ancho de 1080 -- se escala al ancho real del canvas en pantalla.
            fontSize: `${(overlay.font_size / 1080) * 100}cqw`,
            ...textOverlayStyle(overlay),
          }}
        >
          {overlay.text || 'Texto'}
        </div>
      ))}
      {emojiOverlays?.map((overlay) => {
        const src = emojiImageUrls?.[overlay.emoji_id]
        if (!src) return null
        return (
          <img
            key={overlay.id}
            src={src}
            alt=""
            draggable={false}
            onMouseDown={(event) => {
              onSelectEmoji?.(overlay.id)
              handlePointerDown(event, (x, y) => onMoveEmoji?.(overlay.id, x, y))
            }}
            className={cn(
              'absolute -translate-x-1/2 -translate-y-1/2 cursor-grab active:cursor-grabbing',
              overlay.id === selectedEmojiId && 'outline outline-2 outline-dashed outline-primary',
            )}
            style={{
              left: `${overlay.x * 100}%`,
              top: `${overlay.y * 100}%`,
              width: `${overlay.size * 100}cqw`,
            }}
          />
        )
      })}
      {captionPreview && (
        <div
          onMouseDown={(event) => handlePointerDown(event, (x, y) => onCaptionMove?.(x, y))}
          className="absolute max-w-[85%] -translate-x-1/2 -translate-y-1/2 cursor-grab active:cursor-grabbing whitespace-pre-wrap rounded px-2 py-1 text-center text-sm font-semibold"
          style={{
            left: `${captionPreview.x * 100}%`,
            top: `${captionPreview.y * 100}%`,
            ...(captionPreview.highlightStyle === 'text_color'
              ? { color: captionPreview.bgColor, textShadow: '0 0 3px rgba(0,0,0,0.9)' }
              : captionPreview.highlightStyle === 'karaoke'
                ? { color: '#FFFFFF', textShadow: '0 0 3px rgba(0,0,0,0.9)' }
                : captionPreview.highlightStyle === 'karaoke_background'
                  ? { color: captionPreview.textColor, textShadow: '0 0 3px rgba(0,0,0,0.9)' }
                  : { color: captionPreview.textColor, backgroundColor: captionPreview.bgColor }),
          }}
        >
          {captionPreview.highlightStyle === 'karaoke' || captionPreview.highlightStyle === 'karaoke_background' ? (
            // Preview estatico (no hay reproduccion real en el editor):
            // aproxima "se resalta la palabra que se esta narrando"
            // resaltando la PRIMERA palabra del texto de ejemplo (ver RM-25)
            // -- con un cambio de color o una caja de fondo, segun el estilo.
            (() => {
              const [firstWord, ...rest] = captionPreview.text.split(' ')
              return (
                <>
                  <span
                    style={
                      captionPreview.highlightStyle === 'karaoke_background'
                        ? { backgroundColor: captionPreview.bgColor, borderRadius: 4, padding: '0 0.2em' }
                        : { color: captionPreview.bgColor }
                    }
                  >
                    {firstWord}
                  </span>
                  {rest.length > 0 ? ` ${rest.join(' ')}` : ''}
                </>
              )
            })()
          ) : (
            captionPreview.text
          )}
        </div>
      )}
    </div>
  )
}
