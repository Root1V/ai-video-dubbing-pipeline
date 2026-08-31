"""Caso de uso: GenerateMicroVideoUseCase.

Genera un micro-video vertical para redes sociales a partir de una imagen y
un texto: la imagen queda de fondo con un efecto Ken Burns (zoom lento), el
texto se narra con TTS (mismo `SpeechSynthesizer`/particionado en fragmentos
que `SynthesizeTextUseCase`) y se incrusta como captions sincronizados con la
narracion. No usa ningun modelo de generacion de imagen/video -- toda la
composicion es ffmpeg (`MediaProcessor`), ver RM-14 en docs/roadmap.md para
la alternativa con video generado por IA (RM-22).
"""

from __future__ import annotations

import re
from pathlib import Path

from video_translator.application.interfaces import MediaProcessor, SpeechSynthesizer
from video_translator.application.use_cases.text_chunking import split_into_chunks
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import (
    GenerateMicroVideoRequest,
    GenerateMicroVideoResult,
    TextOverlay,
    TranslatedSegment,
)
from video_translator.utils.logging_config import get_logger
from video_translator.utils.timing import PipelineTimings

logger = get_logger(__name__)

DEFAULT_MAX_CHUNK_CHARS = 500
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
# Los fragmentos de TTS (hasta DEFAULT_MAX_CHUNK_CHARS) son del tamano
# correcto para sintetizar, pero un caption con cientos de caracteres
# aparece como un bloque estatico que cubre buena parte de la pantalla en
# vez de acompañar el habla. Los captions se generan aparte, mas cortos,
# repartiendo la duracion real de cada fragmento entre sus propios captions
# (ver _build_caption_segments).
CAPTION_MAX_CHARS = 50
# Estilo de los captions (ver _write_ass_captions): Alignment=2 (centrado,
# abajo), BorderStyle=3 (caja solida) porque texto blanco con solo contorno
# se pierde sobre una imagen de fondo clara/blanca -- una caja resaltada
# (color elegible por el usuario) garantiza contraste sin importar el fondo.
CAPTION_FONT_SIZE = 52
CAPTION_MARGIN_V = 160
# Opacidad de la caja de fondo (00 = opaco, FF = transparente en ASS).
# Probado en la practica: libass (via el filtro "ass" de ffmpeg) NO mezcla
# bien un BackColour semi-transparente con el video de fondo -- el resultado
# sale oscuro/incorrecto sin importar el color elegido, sea cual sea el
# alpha intermedio. Opaco evita ese problema y es igual de legible.
CAPTION_BG_ALPHA_HEX = "00"
# Duracion del fade in/out de un overlay con TextOverlay.fade=True (ver
# _build_overlay_style_and_dialogue), clampeada para videos muy cortos.
OVERLAY_FADE_MS = 500

# "**palabra**" se resalta en negrita en el caption (no se lee en voz alta:
# ver _strip_bold_markers, usado para el texto que va al sintetizador).
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")


def _strip_bold_markers(text: str) -> str:
    return _BOLD_PATTERN.sub(r"\1", text)


def _convert_bold_to_ass(text: str) -> str:
    return _BOLD_PATTERN.sub(r"{\\b1}\1{\\b0}", text)


def _hex_to_ass_color(hex_color: str) -> str:
    """Convierte "#RRGGBB" al formato de color de ASS: &HAABBGGRR (orden BGR,
    alpha primero, siempre opaco -- ver CAPTION_BG_ALPHA_HEX). Si el valor no
    es un hex valido, cae a negro solido."""
    value = hex_color.lstrip("#")
    if len(value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in value):
        value = "000000"
    rr, gg, bb = value[0:2], value[2:4], value[4:6]
    return f"&H{CAPTION_BG_ALPHA_HEX}{bb}{gg}{rr}"


class GenerateMicroVideoUseCase:
    def __init__(
        self,
        speech_synthesizer: SpeechSynthesizer,
        media_processor: MediaProcessor,
        default_speaker_reference_wav: Path,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
        effective_config: dict | None = None,
    ) -> None:
        self._synthesizer = speech_synthesizer
        self._media = media_processor
        self._default_speaker_wav = default_speaker_reference_wav
        self._max_chunk_chars = max_chunk_chars
        self._effective_config = dict(effective_config) if effective_config else {}

    def execute(self, request: GenerateMicroVideoRequest) -> GenerateMicroVideoResult:
        self._validate_request(request)
        request.output_dir.mkdir(parents=True, exist_ok=True)
        workdir = request.output_dir / "_work"
        chunk_dir = workdir / "tts_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        report_path = request.output_dir / "pipeline_timings.json"
        timings = PipelineTimings(report_path=report_path)
        if self._effective_config:
            timings.set_effective_config(**self._effective_config)
        log = logger.bind(run_id=timings.run_id)
        log.info("generate_micro_video.start", chars=len(request.text))

        speaker_wav = request.speaker_reference_wav or self._default_speaker_wav

        chunks = split_into_chunks(request.text, self._max_chunk_chars)
        segments: list[tuple[float, Path, float]] = []
        cursor = 0.0
        with timings.stage("text_to_speech", num_chunks=len(chunks)):
            for i, chunk_text in enumerate(chunks):
                chunk_path = chunk_dir / f"chunk_{i:03d}.wav"
                self._synthesizer.synthesize_segment(
                    text=_strip_bold_markers(chunk_text),
                    output_path=chunk_path,
                    target_duration_seconds=0.0,
                    speaker_reference_wav=speaker_wav,
                    language=request.language,
                )
                chunk_duration = self._media.get_duration_seconds(chunk_path)
                segments.append((cursor, chunk_path, chunk_duration))
                cursor += chunk_duration
        log.info("generate_micro_video.narration_done", num_chunks=len(chunks))

        narration_path = workdir / "narration.wav"
        with timings.stage("audio_concatenation"):
            self._synthesizer.concatenate_segments(segments, cursor, narration_path)

        # Duracion fija elegida por el usuario (ver RM-14): si la narracion
        # se paso, se acelera el audio entero para que encaje (nunca se
        # recorta -- ver MediaProcessor.fit_audio_to_duration) y los
        # timestamps de los captions ya calculados se reescalan en la misma
        # proporcion para seguir sincronizados. Si la narracion es mas corta,
        # el video queda con la duracion fija igual (el Ken Burns sigue
        # corriendo en silencio el tiempo restante, ver render_image_video).
        video_duration = cursor
        if request.target_duration_seconds is not None:
            target = request.target_duration_seconds
            if cursor > target > 0:
                with timings.stage("narration_speedup", original_seconds=round(cursor, 2), target_seconds=target):
                    self._media.fit_audio_to_duration(narration_path, target)
                speed_factor = cursor / target
                segments = [(start / speed_factor, path, duration / speed_factor) for start, path, duration in segments]
                cursor = target
            video_duration = target

        if request.narration_volume != 1.0:
            with timings.stage("narration_volume"):
                self._media.apply_volume(narration_path, request.narration_volume)

        final_audio_path = narration_path
        if request.background_music_path is not None:
            music_path = request.background_music_path
            # Rango elegido por el usuario dentro de la pista (ver RM-28): se
            # recorta una vez a un archivo aparte, que es lo que despues se
            # loopea/mezcla -- mix_background_music no cambia, solo recibe
            # ya el fragmento correcto en vez de la pista completa.
            if request.background_music_start > 0 or request.background_music_end is not None:
                music_range_path = workdir / "background_music_range.wav"
                with timings.stage("background_music_trim"):
                    self._media.extract_music_range(
                        music_path,
                        request.background_music_start,
                        request.background_music_end or self._media.get_duration_seconds(music_path),
                        music_range_path,
                    )
                music_path = music_range_path
            mixed_audio_path = workdir / "narration_with_music.wav"
            with timings.stage("background_music"):
                self._media.mix_background_music(
                    narration_path,
                    music_path,
                    mixed_audio_path,
                    duration_seconds=video_duration,
                    music_volume=request.background_music_volume,
                )
            final_audio_path = mixed_audio_path

        caption_segments = _build_caption_segments(
            [(chunk_text, start, duration) for chunk_text, (start, _path, duration) in zip(chunks, segments)]
        )
        captions_path = workdir / "captions.ass"
        with timings.stage("caption_writing"):
            _write_ass_captions(
                caption_segments,
                captions_path,
                VIDEO_WIDTH,
                VIDEO_HEIGHT,
                request.caption_bg_color,
                request.caption_highlight_style,
                overlays=request.text_overlays,
                duration=video_duration,
                caption_x=request.caption_x,
                caption_y=request.caption_y,
            )

        background_path = workdir / "background.mp4"
        with timings.stage("image_to_video"):
            self._media.render_image_video(
                request.image_path,
                final_audio_path,
                background_path,
                duration_seconds=video_duration,
                width=VIDEO_WIDTH,
                height=VIDEO_HEIGHT,
            )

        output_video = request.output_dir / "micro_video.mp4"
        with timings.stage("caption_burn"):
            self._media.render_ass_captions(background_path, captions_path, output_video)

        timings.set_outputs(video_bytes=output_video.stat().st_size)
        timings.write_report(report_path, final=True)
        log.info(
            "generate_micro_video.finished",
            total_seconds=round(timings.total_seconds, 1),
            timings_report=str(report_path),
        )

        return GenerateMicroVideoResult(
            output_video=output_video,
            duration_seconds=video_duration,
            timings=timings.as_dict(),
        )

    @staticmethod
    def _validate_request(request: GenerateMicroVideoRequest) -> None:
        if not request.text.strip():
            raise VideoTranslatorError("El texto a narrar esta vacio.")
        if not request.image_path.exists():
            raise InvalidVideoFileError(f"No existe el archivo: {request.image_path}")
        if request.image_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise InvalidVideoFileError(
                f"Extension de imagen no soportada '{request.image_path.suffix}'. "
                f"Soportadas: {sorted(SUPPORTED_IMAGE_EXTENSIONS)}"
            )


def _build_caption_segments(chunks_with_timing: list[tuple[str, float, float]]) -> list[TranslatedSegment]:
    """Convierte los fragmentos de TTS (texto, inicio, duracion) en captions
    mas cortos y con mas movimiento: cada fragmento se vuelve a partir en
    piezas de hasta CAPTION_MAX_CHARS, repartiendo la duracion real del
    fragmento entre sus piezas en proporcion a su cantidad de caracteres.

    No hay timestamps por palabra del motor de TTS -- esto es una
    aproximacion (asume ritmo de habla uniforme dentro de un mismo
    fragmento), pero alcanza para que los captions vayan apareciendo y
    desapareciendo con el habla en vez de mostrar todo el texto de un
    fragmento de golpe durante toda su duracion."""
    segments: list[TranslatedSegment] = []
    seg_id = 0
    for chunk_text, chunk_start, chunk_duration in chunks_with_timing:
        pieces = _split_caption_text(chunk_text, CAPTION_MAX_CHARS)
        total_chars = sum(len(piece) for piece in pieces) or 1
        cursor = chunk_start
        for piece in pieces:
            piece_duration = chunk_duration * (len(piece) / total_chars)
            segments.append(
                TranslatedSegment(
                    id=seg_id,
                    start=cursor,
                    end=cursor + piece_duration,
                    source_text=piece,
                    translated_text=piece,
                )
            )
            seg_id += 1
            cursor += piece_duration
    return segments


def _split_caption_text(text: str, max_chars: int) -> list[str]:
    """Como `split_into_chunks`, pero garantiza que ninguna pieza supere
    `max_chars`: esa funcion solo parte ENTRE oraciones, asi que una sola
    oracion larga (sin puntos internos) queda intacta aunque exceda el
    limite -- para un caption eso es exactamente el bug que se busca evitar
    (todo el texto en un solo cartel). Las piezas que aun excedan el limite
    se vuelven a partir por palabra, de forma codiciosa."""
    pieces: list[str] = []
    for sentence_piece in split_into_chunks(text, max_chars):
        if len(sentence_piece) <= max_chars:
            pieces.append(sentence_piece)
            continue
        words = sentence_piece.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) > max_chars and current:
                pieces.append(current)
                current = word
            else:
                current = candidate
        if current:
            pieces.append(current)
    return pieces


def _build_caption_style(highlight_style: str, color: str) -> str:
    """Arma la linea "Style:" de ASS segun el estilo de resaltado elegido:

    "background" (default): texto blanco sobre una caja opaca del color
    elegido (BorderStyle=3). OutlineColour se fija IGUAL a BackColour a
    proposito: probado en la practica, en BorderStyle=3 esta version de
    libass rellena la caja con OutlineColour, no con BackColour como sugiere
    la documentacion -- dejarlo en un color fijo (p.ej. negro) hacia que la
    caja saliera siempre negra sin importar el color elegido.

    "text_color": el texto queda del color elegido, sin caja -- solo un
    contorno negro (BorderStyle=1) para que se lea sobre cualquier fondo.
    """
    ass_color = _hex_to_ass_color(color)
    if highlight_style == "text_color":
        # PrimaryColour, SecondaryColour, OutlineColour, BackColour
        colours = f"{ass_color},&H000000FF,&H00000000,&H00000000"
        border_style, outline, shadow = 1, 3, 1
    else:
        colours = f"&H00FFFFFF,&H000000FF,{ass_color},{ass_color}"
        border_style, outline, shadow = 3, 2, 0
    return (
        f"Style: Default,Arial,{CAPTION_FONT_SIZE},{colours},"
        # Alignment=5 (centro): el \pos(x,y) de cada Dialogue (ver
        # _write_ass_captions) posiciona el CENTRO del caption, igual
        # criterio que los overlays de texto -- arrastrable en el editor.
        f"0,0,0,0,100,100,0,0,{border_style},{outline},{shadow},5,60,60,{CAPTION_MARGIN_V},1"
    )


def _write_ass_captions(
    segments: list[TranslatedSegment],
    output_path: Path,
    width: int,
    height: int,
    color: str,
    highlight_style: str,
    overlays: list[TextOverlay] | None = None,
    duration: float = 0.0,
    caption_x: float = 0.5,
    caption_y: float = 0.85,
) -> Path:
    """Escribe los captions como .ass (no .srt) con un header propio que
    declara `PlayResX`/`PlayResY` igual al tamano real del video: sin esto,
    libass asume una resolucion de guion vieja (384x288) al renderizar un
    .srt "plano" y reescala el font al tamano real del video, lo que en un
    vertical de alta resolucion (1080x1920) termina en un texto gigante que
    cubre la pantalla.

    `overlays` (ver RM-28, textos libres posicionados a mano) se agregan al
    MISMO script: cada uno con su propio `Style:` (fuente/tamano/color/
    negrita propios) y una unica `Dialogue:` que dura todo el video, usando
    `\\pos(x,y)` para la posicion absoluta -- no hace falta ningun filtro de
    ffmpeg nuevo, `render_ass_captions` ya sabe renderizar esto tal cual."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    style = _build_caption_style(highlight_style, color)
    overlay_styles: list[str] = []
    overlay_dialogues: list[str] = []
    for i, overlay in enumerate(overlays or []):
        overlay_style, overlay_dialogue = _build_overlay_style_and_dialogue(overlay, i, width, height, duration)
        overlay_styles.append(overlay_style)
        overlay_dialogues.append(overlay_dialogue)

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        style,
        *overlay_styles,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        # Los overlays van ANTES que los captions en la lista de eventos: en
        # el mismo Layer, libass dibuja en el orden declarado, asi que esto
        # deja los captions (la narracion) siempre por encima de un overlay
        # que pudiera superponerse en la misma zona de la pantalla.
        *overlay_dialogues,
    ]
    pos_tag = "{" + _ass_pos_tag(caption_x, caption_y, width, height) + "}"
    for seg in segments:
        # Se despojan llaves literales ANTES de convertir "**negrita**" a
        # tags ASS ("{\b1}...{\b0}") -- de lo contrario un usuario que
        # escriba "{" a proposito podria inyectar sus propios overrides ASS.
        raw_text = seg.translated_text.replace("{", "").replace("}", "").replace("\n", " ")
        text = pos_tag + _convert_bold_to_ass(raw_text)
        lines.append(
            f"Dialogue: 0,{_format_ass_timestamp(seg.start)},{_format_ass_timestamp(seg.end)},"
            f"Default,,0,0,0,,{text}"
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _escape_overlay_text(text: str) -> str:
    """Escapa el texto libre de un TextOverlay para el campo Text de un
    Dialogue ASS: quita llaves literales (evita que el usuario inyecte sus
    propios override tags) y convierte saltos de linea reales en el salto
    de linea nativo de ASS (\\N) -- a diferencia de los captions (generados
    automaticamente, nunca traen un salto de linea real), un overlay es
    texto libre donde preservar el salto que el usuario escribio importa."""
    return text.replace("{", "").replace("}", "").replace("\r\n", "\n").replace("\n", "\\N")


def _ass_pos_tag(x: float, y: float, width: int, height: int) -> str:
    """Fragmento de override tag `\\pos(x,y)` en pixeles absolutos, a partir
    de fracciones 0-1 del ancho/alto del video -- reusado por los overlays
    de texto y por los captions de la narracion (ambos "arrastrables" en el
    editor con el mismo criterio: el punto es el CENTRO del texto)."""
    return f"\\pos({round(x * width)},{round(y * height)})"


def _build_overlay_style_and_dialogue(
    overlay: TextOverlay, index: int, width: int, height: int, duration: float
) -> tuple[str, str]:
    """Arma el `Style:`/`Dialogue:` de un TextOverlay: Alignment=5 (centro)
    para que `\\pos(x,y)` posicione el CENTRO del texto en (x,y) -- coincide
    con "donde se soltó el texto al arrastrarlo" en el editor. BorderStyle=1
    con contorno negro (mismo criterio que el estilo "text_color" de los
    captions) para que se lea sobre cualquier fondo sin importar el color
    elegido."""
    style_name = f"Overlay{index}"
    ass_color = _hex_to_ass_color(overlay.color)
    bold_flag = -1 if overlay.bold else 0
    style = (
        f"Style: {style_name},{overlay.font_family},{overlay.font_size},"
        f"{ass_color},&H000000FF,&H00000000,&H00000000,"
        f"{bold_flag},0,0,0,100,100,0,0,1,3,1,5,0,0,0,1"
    )
    override = "{" + _ass_pos_tag(overlay.x, overlay.y, width, height)
    if overlay.fade:
        fade_ms = max(1, min(OVERLAY_FADE_MS, int(duration * 1000 / 4)))
        override += f"\\fad({fade_ms},{fade_ms})"
    override += "}"
    text = override + _escape_overlay_text(overlay.text)
    dialogue = (
        f"Dialogue: 0,{_format_ass_timestamp(0)},{_format_ass_timestamp(duration)},"
        f"{style_name},,0,0,0,,{text}"
    )
    return style, dialogue


def _format_ass_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    total_centis = round(seconds * 100)
    hours, rem = divmod(total_centis, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, centis = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"
