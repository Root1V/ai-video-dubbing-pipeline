"""Tests de GenerateMicroVideoUseCase usando fakes en memoria (mismo patron
que test_synthesize_text_use_case.py)."""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from video_translator.application.use_cases.generate_micro_video import GenerateMicroVideoUseCase
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import GenerateMicroVideoRequest, TextOverlay


class FakeMediaProcessor:
    """Solo implementa lo que GenerateMicroVideoUseCase necesita de
    MediaProcessor. get_duration_seconds devuelve una duracion fija por
    caracter para que el timing de los segmentos sea verificable."""

    def __init__(self):
        self.render_calls: list[dict] = []
        self.caption_calls: list[dict] = []
        self.fit_calls: list[dict] = []
        self.music_calls: list[dict] = []
        self.music_range_calls: list[dict] = []
        self.volume_calls: list[dict] = []

    def get_duration_seconds(self, media_path: Path) -> float:
        return 1.0

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def attach_soft_subtitles(self, video_path: Path, srt_path: Path, output_path: Path, lang_code: str = "spa") -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def clean_music_track(self, input_path: Path, output_wav: Path) -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def extract_music_range(self, track_path: Path, start: float, end: float, output_path: Path) -> Path:
        self.music_range_calls.append({"track_path": track_path, "start": start, "end": end})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-music-range")
        return output_path

    def apply_volume(self, audio_path: Path, volume: float) -> None:
        self.volume_calls.append({"audio_path": audio_path, "volume": volume})

    def replace_audio_track(
        self, video_path: Path, new_audio_path: Path, output_path: Path, keep_original_as_secondary: bool = True
    ) -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def render_image_video(
        self, image_path: Path, audio_path: Path, output_path: Path, duration_seconds: float,
        width: int = 1080, height: int = 1920,
    ) -> Path:
        self.render_calls.append(
            {
                "image_path": image_path,
                "audio_path": audio_path,
                "duration_seconds": duration_seconds,
                "width": width,
                "height": height,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-background-video")
        return output_path

    def render_ass_captions(self, video_path: Path, ass_path: Path, output_path: Path) -> Path:
        self.caption_calls.append({"video_path": video_path, "ass_path": ass_path})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-final-video")
        return output_path

    def fit_audio_to_duration(self, audio_path: Path, target_seconds: float) -> bool:
        self.fit_calls.append({"audio_path": audio_path, "target_seconds": target_seconds})
        return True

    def mix_background_music(
        self, narration_path: Path, music_path: Path, output_path: Path,
        duration_seconds: float, music_volume: float = 0.12,
    ) -> Path:
        self.music_calls.append(
            {
                "narration_path": narration_path,
                "music_path": music_path,
                "duration_seconds": duration_seconds,
                "music_volume": music_volume,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-mixed-audio")
        return output_path


class FakeSpeechSynthesizer:
    def __init__(self):
        self.calls: list[dict] = []
        self.concatenated: list[tuple] = []

    def synthesize_segment(self, text, output_path, target_duration_seconds, speaker_reference_wav=None, language="es"):
        self.calls.append({"text": text, "speaker_reference_wav": speaker_reference_wav, "language": language})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-wav")
        return output_path

    def concatenate_segments(self, segment_audio_paths, total_duration, output_path):
        self.concatenated.append((list(segment_audio_paths), total_duration))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-narration-wav")
        return output_path


DEFAULT_VOICE = Path("/fake/default_voice.wav")


def _make_use_case(media=None, synthesizer=None, max_chunk_chars=500):
    return GenerateMicroVideoUseCase(
        speech_synthesizer=synthesizer or FakeSpeechSynthesizer(),
        media_processor=media or FakeMediaProcessor(),
        default_speaker_reference_wav=DEFAULT_VOICE,
        max_chunk_chars=max_chunk_chars,
    )


def _make_image(tmp_path: Path) -> Path:
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-image-bytes")
    return image_path


_DIALOGUE_RE = re.compile(
    r"^Dialogue: \d+,(?P<start>[\d:.]+),(?P<end>[\d:.]+),Default,,0,0,0,,(?P<text>.*)$"
)


def _ass_timestamp_to_seconds(value: str) -> float:
    hours, minutes, rest = value.split(":")
    secs, centis = rest.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(centis) / 100


_LEADING_OVERRIDE_TAG_RE = re.compile(r"^\{[^}]*\}")


def _read_ass_dialogues(ass_path: Path) -> list[tuple[float, float, str]]:
    dialogues = []
    for line in ass_path.read_text(encoding="utf-8").splitlines():
        match = _DIALOGUE_RE.match(line)
        if match:
            # Todo caption ahora arranca con un override tag "{\pos(x,y)}"
            # (ver _ass_pos_tag) -- se descarta para estos tests, que
            # verifican el TEXTO/timing de los captions, no su posicion.
            text = _LEADING_OVERRIDE_TAG_RE.sub("", match.group("text"))
            dialogues.append(
                (
                    _ass_timestamp_to_seconds(match.group("start")),
                    _ass_timestamp_to_seconds(match.group("end")),
                    text,
                )
            )
    return dialogues


def test_execute_produces_video_using_default_voice(tmp_path: Path):
    media = FakeMediaProcessor()
    synthesizer = FakeSpeechSynthesizer()
    use_case = _make_use_case(media=media, synthesizer=synthesizer)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola mundo.", output_dir=tmp_path / "out")

    result = use_case.execute(request)

    assert result.output_video == tmp_path / "out" / "micro_video.mp4"
    assert result.output_video.exists()
    assert synthesizer.calls[0]["speaker_reference_wav"] == DEFAULT_VOICE
    assert media.render_calls[0]["image_path"] == image_path
    # render_ass_captions debe recibir el video de fondo que produjo render_image_video.
    assert media.caption_calls[0]["video_path"].name == "background.mp4"


def test_execute_uses_own_speaker_reference_when_provided(tmp_path: Path):
    synthesizer = FakeSpeechSynthesizer()
    use_case = _make_use_case(synthesizer=synthesizer)
    image_path = _make_image(tmp_path)
    own_voice = tmp_path / "my_voice.wav"
    request = GenerateMicroVideoRequest(
        image_path=image_path, text="Hola mundo.", output_dir=tmp_path / "out", speaker_reference_wav=own_voice
    )

    use_case.execute(request)

    assert synthesizer.calls[0]["speaker_reference_wav"] == own_voice


def test_execute_writes_ass_captions_with_video_resolution(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola.", output_dir=tmp_path / "out")

    use_case.execute(request)

    ass_path = media.caption_calls[0]["ass_path"]
    content = ass_path.read_text(encoding="utf-8")
    # PlayResX/PlayResY deben coincidir con el video real -- sin esto libass
    # reescala el font (bug original: el texto cubria toda la pantalla).
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content


def test_execute_writes_captions_matching_narration_chunks(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media, max_chunk_chars=20)
    image_path = _make_image(tmp_path)
    long_text = "Primera oracion corta. Segunda oracion tambien corta. Tercera oracion mas."
    request = GenerateMicroVideoRequest(image_path=image_path, text=long_text, output_dir=tmp_path / "out")

    use_case.execute(request)

    dialogues = _read_ass_dialogues(media.caption_calls[0]["ass_path"])
    assert len(dialogues) > 1
    # Los segmentos de captions no deben solaparse ni dejar huecos (cada uno
    # dura 1.0s segun FakeMediaProcessor).
    for i, (start, end, _text) in enumerate(dialogues):
        assert start == pytest.approx(float(i), abs=0.01)
        assert end == pytest.approx(float(i) + 1.0, abs=0.01)


def test_execute_splits_a_single_narration_chunk_into_several_short_captions(tmp_path: Path):
    # max_chunk_chars grande -> todo el texto entra en UN solo fragmento de
    # TTS (una sola llamada al sintetizador), pero el texto es mas largo que
    # CAPTION_MAX_CHARS: debe verse igual dividido en varios captions cortos,
    # no como un unico cartel con todo el texto durante los 3s enteros.
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media, max_chunk_chars=500)
    image_path = _make_image(tmp_path)
    long_text = (
        "Esta es una oracion bastante larga que deberia partirse en varios "
        "captions cortos en vez de mostrarse entera de una sola vez."
    )
    request = GenerateMicroVideoRequest(image_path=image_path, text=long_text, output_dir=tmp_path / "out")

    use_case.execute(request)

    dialogues = _read_ass_dialogues(media.caption_calls[0]["ass_path"])
    assert len(dialogues) > 1
    for _start, _end, text in dialogues:
        assert len(text) <= 50
    # Deben cubrir en fila la duracion total del fragmento de TTS (1.0s segun
    # FakeMediaProcessor), sin solaparse ni dejar huecos.
    assert dialogues[0][0] == pytest.approx(0.0, abs=0.01)
    assert dialogues[-1][1] == pytest.approx(1.0, abs=0.01)
    for prev, nxt in pairwise(dialogues):
        assert prev[1] == pytest.approx(nxt[0], abs=0.01)


def test_execute_does_not_mix_music_by_default(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola.", output_dir=tmp_path / "out")

    use_case.execute(request)

    assert media.music_calls == []
    # Sin musica, el audio narrado se pasa directo a render_image_video.
    assert media.render_calls[0]["audio_path"].name == "narration.wav"


def test_execute_mixes_background_music_when_requested(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    music_path = tmp_path / "track.mp3"
    music_path.write_bytes(b"fake-music-bytes")
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        target_duration_seconds=5.0,
        background_music_path=music_path,
    )

    use_case.execute(request)

    assert len(media.music_calls) == 1
    assert media.music_calls[0]["music_path"] == music_path
    assert media.music_calls[0]["narration_path"].name == "narration.wav"
    # Se mezcla usando la duracion FINAL del video (la fija elegida), no la
    # duracion cruda de la narracion.
    assert media.music_calls[0]["duration_seconds"] == pytest.approx(5.0)
    # render_image_video debe recibir el audio YA MEZCLADO, no la narracion sola.
    assert media.render_calls[0]["audio_path"].name == "narration_with_music.wav"


def test_execute_renders_at_vertical_resolution(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola.", output_dir=tmp_path / "out")

    use_case.execute(request)

    assert media.render_calls[0]["width"] == 1080
    assert media.render_calls[0]["height"] == 1920


def test_execute_strips_bold_markers_from_narration_but_keeps_them_for_captions(tmp_path: Path):
    media = FakeMediaProcessor()
    synthesizer = FakeSpeechSynthesizer()
    use_case = _make_use_case(media=media, synthesizer=synthesizer)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(
        image_path=image_path, text="Esto **es lo mejor** de la industria.", output_dir=tmp_path / "out"
    )

    use_case.execute(request)

    # El sintetizador no debe recibir los asteriscos (no se los debe "leer").
    assert "**" not in synthesizer.calls[0]["text"]
    assert "es lo mejor" in synthesizer.calls[0]["text"]
    # El caption si debe convertir el texto resaltado a negrita ASS.
    dialogues = _read_ass_dialogues(media.caption_calls[0]["ass_path"])
    full_caption_text = " ".join(text for _s, _e, text in dialogues)
    assert r"{\b1}es lo mejor{\b0}" in full_caption_text
    assert "**" not in full_caption_text


def test_execute_writes_chosen_caption_background_color(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(
        image_path=image_path, text="Hola.", output_dir=tmp_path / "out", caption_bg_color="#FF0000"
    )

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    # "#FF0000" (rojo) en ASS es BGR, opaco: &H000000FF.
    assert "&H000000FF" in content
    # Estilo "background" (default): sin pasar caption_highlight_style, debe
    # quedar el texto blanco y BorderStyle=3 (caja).
    style_line = next(line for line in content.splitlines() if line.startswith("Style:"))
    assert style_line.split(",")[3] == "&H00FFFFFF"  # PrimaryColour blanco
    assert style_line.split(",")[15] == "3"  # BorderStyle


def test_execute_writes_text_color_highlight_style_without_a_box(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        caption_bg_color="#00FF00",
        caption_highlight_style="text_color",
    )

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    style_line = next(line for line in content.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    # "#00FF00" (verde) en ASS es BGR, opaco: &H0000FF00 -- ahora en
    # PrimaryColour (el texto), no en BackColour/OutlineColour.
    assert fields[3] == "&H0000FF00"
    assert fields[15] == "1"  # BorderStyle=1 (sin caja, solo contorno)


def test_execute_holds_the_image_when_narration_is_shorter_than_target_duration(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)  # cada fragmento dura 1.0s (FakeMediaProcessor)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(
        image_path=image_path, text="Hola.", output_dir=tmp_path / "out", target_duration_seconds=10.0
    )

    result = use_case.execute(request)

    # El video dura la duracion elegida (10s), no se acelera el audio (mas
    # corto que su hueco -- se mantiene la imagen el resto del tiempo).
    assert result.duration_seconds == pytest.approx(10.0)
    assert media.render_calls[0]["duration_seconds"] == pytest.approx(10.0)
    assert media.fit_calls == []


def test_execute_speeds_up_narration_when_longer_than_target_duration(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media, max_chunk_chars=20)  # fuerza varios fragmentos de 1.0s c/u
    image_path = _make_image(tmp_path)
    long_text = "Primera oracion corta. Segunda oracion tambien corta. Tercera oracion mas."
    request = GenerateMicroVideoRequest(
        image_path=image_path, text=long_text, output_dir=tmp_path / "out", target_duration_seconds=1.5
    )

    result = use_case.execute(request)

    assert len(media.fit_calls) == 1
    assert media.fit_calls[0]["target_seconds"] == pytest.approx(1.5)
    assert result.duration_seconds == pytest.approx(1.5)
    assert media.render_calls[0]["duration_seconds"] == pytest.approx(1.5)
    # Los captions deben quedar reescalados dentro de la duracion final, no
    # seguir apuntando a los timestamps originales (mas largos).
    dialogues = _read_ass_dialogues(media.caption_calls[0]["ass_path"])
    assert dialogues[-1][1] <= 1.5 + 0.05


def test_execute_rejects_empty_text(tmp_path: Path):
    use_case = _make_use_case()
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="   ", output_dir=tmp_path / "out")

    with pytest.raises(VideoTranslatorError):
        use_case.execute(request)


def test_execute_rejects_missing_image(tmp_path: Path):
    use_case = _make_use_case()
    request = GenerateMicroVideoRequest(
        image_path=tmp_path / "does_not_exist.jpg", text="Hola.", output_dir=tmp_path / "out"
    )

    with pytest.raises(InvalidVideoFileError):
        use_case.execute(request)


def test_execute_rejects_unsupported_image_extension(tmp_path: Path):
    use_case = _make_use_case()
    bad_image = tmp_path / "clip.mp4"
    bad_image.write_bytes(b"not-an-image")
    request = GenerateMicroVideoRequest(image_path=bad_image, text="Hola.", output_dir=tmp_path / "out")

    with pytest.raises(InvalidVideoFileError):
        use_case.execute(request)


def test_execute_without_overlays_adds_no_overlay_style_or_dialogue(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola.", output_dir=tmp_path / "out")

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    assert "Overlay0" not in content


def test_execute_writes_overlay_position_bold_color_and_font(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    overlay = TextOverlay(
        text="Hola mundo",
        x=0.25,
        y=0.5,
        bold=True,
        font_family="Impact",
        font_size=64,
        color="#00FF00",
    )
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        text_overlays=[overlay],
    )

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    # Style: negrita (-1), tipografia y tamano elegidos.
    style_line = next(line for line in content.splitlines() if line.startswith("Style: Overlay0"))
    fields = style_line.split(",")
    assert fields[1] == "Impact"
    assert fields[2] == "64"
    assert fields[7] == "-1"  # Bold
    # x=0.25*1080=270, y=0.5*1920=960 (ver VIDEO_WIDTH/VIDEO_HEIGHT en _make_use_case).
    dialogue_line = next(line for line in content.splitlines() if line.startswith("Dialogue: 0,0:00:00.00"))
    assert "\\pos(270,960)" in dialogue_line
    assert "Hola mundo" in dialogue_line
    assert "\\fad(" not in dialogue_line


def test_execute_writes_overlay_fade_when_requested(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    overlay = TextOverlay(text="Con fade", x=0.5, y=0.1, fade=True)
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        target_duration_seconds=5.0,  # suficientemente largo para no clampear el fade de 500ms
        text_overlays=[overlay],
    )

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    dialogue_line = next(line for line in content.splitlines() if "Con fade" in line)
    assert "\\fad(500,500)" in dialogue_line


def test_execute_clamps_overlay_fade_duration_for_short_videos(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    # FakeMediaProcessor.get_duration_seconds -> 1.0s de narracion (un solo
    # chunk): sin clamp, un fade de 500ms in + 500ms out excederia el video.
    overlay = TextOverlay(text="Corto", x=0.5, y=0.1, fade=True)
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        text_overlays=[overlay],
    )

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    dialogue_line = next(line for line in content.splitlines() if "Corto" in line)
    assert "\\fad(250,250)" in dialogue_line


def test_execute_escapes_overlay_braces_and_preserves_line_breaks(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    overlay = TextOverlay(text="Linea 1\nLinea {2}", x=0.5, y=0.5)
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        text_overlays=[overlay],
    )

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    assert "Linea 1\\NLinea 2" in content
    assert "{2}" not in content


def test_execute_does_not_extract_music_range_when_using_full_track(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    music_path = tmp_path / "track.mp3"
    music_path.write_bytes(b"fake-music-bytes")
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        target_duration_seconds=5.0,
        background_music_path=music_path,
    )

    use_case.execute(request)

    assert media.music_range_calls == []
    assert media.music_calls[0]["music_path"] == music_path


def test_execute_extracts_music_range_before_mixing_when_requested(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    music_path = tmp_path / "track.mp3"
    music_path.write_bytes(b"fake-music-bytes")
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        target_duration_seconds=5.0,
        background_music_path=music_path,
        background_music_start=10.0,
        background_music_end=20.0,
    )

    use_case.execute(request)

    assert len(media.music_range_calls) == 1
    assert media.music_range_calls[0]["track_path"] == music_path
    assert media.music_range_calls[0]["start"] == pytest.approx(10.0)
    assert media.music_range_calls[0]["end"] == pytest.approx(20.0)
    # mix_background_music debe recibir el RECORTE, no la pista original.
    assert media.music_calls[0]["music_path"] != music_path
    assert media.music_calls[0]["music_path"].name == "background_music_range.wav"


def test_execute_does_not_apply_narration_volume_by_default(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola.", output_dir=tmp_path / "out")

    use_case.execute(request)

    assert media.volume_calls == []


def test_execute_applies_narration_volume_when_requested(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(
        image_path=image_path, text="Hola.", output_dir=tmp_path / "out", narration_volume=0.5
    )

    use_case.execute(request)

    assert len(media.volume_calls) == 1
    assert media.volume_calls[0]["audio_path"].name == "narration.wav"
    assert media.volume_calls[0]["volume"] == pytest.approx(0.5)


def test_execute_applies_narration_volume_even_without_background_music(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(
        image_path=image_path, text="Hola.", output_dir=tmp_path / "out", narration_volume=1.5
    )

    use_case.execute(request)

    assert media.music_calls == []
    assert len(media.volume_calls) == 1
    assert media.volume_calls[0]["volume"] == pytest.approx(1.5)


def test_execute_passes_background_music_volume_to_mix(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    music_path = tmp_path / "track.mp3"
    music_path.write_bytes(b"fake-music-bytes")
    request = GenerateMicroVideoRequest(
        image_path=image_path,
        text="Hola.",
        output_dir=tmp_path / "out",
        background_music_path=music_path,
        background_music_volume=0.3,
    )

    use_case.execute(request)

    assert media.music_calls[0]["music_volume"] == pytest.approx(0.3)


def test_execute_writes_captions_at_default_position(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola.", output_dir=tmp_path / "out")

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    # default caption_x=0.5, caption_y=0.85 sobre 1080x1920.
    assert "\\pos(540,1632)" in content


def test_execute_writes_captions_at_custom_position(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(
        image_path=image_path, text="Hola.", output_dir=tmp_path / "out", caption_x=0.25, caption_y=0.5
    )

    use_case.execute(request)

    content = media.caption_calls[0]["ass_path"].read_text(encoding="utf-8")
    assert "\\pos(270,960)" in content
