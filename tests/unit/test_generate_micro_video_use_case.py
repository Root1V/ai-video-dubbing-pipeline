"""Tests de GenerateMicroVideoUseCase usando fakes en memoria (mismo patron
que test_synthesize_text_use_case.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_translator.application.use_cases.generate_micro_video import GenerateMicroVideoUseCase
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import GenerateMicroVideoRequest


class FakeMediaProcessor:
    """Solo implementa lo que GenerateMicroVideoUseCase necesita de
    MediaProcessor. get_duration_seconds devuelve una duracion fija por
    caracter para que el timing de los segmentos sea verificable."""

    def __init__(self):
        self.render_calls: list[dict] = []
        self.burn_calls: list[dict] = []

    def get_duration_seconds(self, media_path: Path) -> float:
        return 1.0

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        self.burn_calls.append({"video_path": video_path, "srt_path": srt_path})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-final-video")
        return output_path

    def attach_soft_subtitles(self, video_path: Path, srt_path: Path, output_path: Path, lang_code: str = "spa") -> Path:
        raise NotImplementedError("no usado por GenerateMicroVideoUseCase")

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


class FakeSubtitleWriter:
    def __init__(self):
        self.written_segments: list = []

    def write(self, segments, output_path, use_translation=True):
        self.written_segments = list(segments)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("fake-srt", encoding="utf-8")
        return output_path


DEFAULT_VOICE = Path("/fake/default_voice.wav")


def _make_use_case(media=None, synthesizer=None, subtitles=None, max_chunk_chars=500):
    return GenerateMicroVideoUseCase(
        speech_synthesizer=synthesizer or FakeSpeechSynthesizer(),
        media_processor=media or FakeMediaProcessor(),
        subtitle_writer=subtitles or FakeSubtitleWriter(),
        default_speaker_reference_wav=DEFAULT_VOICE,
        max_chunk_chars=max_chunk_chars,
    )


def _make_image(tmp_path: Path) -> Path:
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-image-bytes")
    return image_path


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
    # burn_subtitles debe recibir el video de fondo que produjo render_image_video.
    assert media.burn_calls[0]["video_path"].name == "background.mp4"


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


def test_execute_writes_captions_matching_narration_chunks(tmp_path: Path):
    subtitles = FakeSubtitleWriter()
    use_case = _make_use_case(subtitles=subtitles, max_chunk_chars=20)
    image_path = _make_image(tmp_path)
    long_text = "Primera oracion corta. Segunda oracion tambien corta. Tercera oracion mas."
    request = GenerateMicroVideoRequest(image_path=image_path, text=long_text, output_dir=tmp_path / "out")

    use_case.execute(request)

    assert len(subtitles.written_segments) > 1
    # Los segmentos de captions no deben solaparse ni dejar huecos (cada uno
    # dura 1.0s segun FakeMediaProcessor).
    for i, seg in enumerate(subtitles.written_segments):
        assert seg.start == pytest.approx(float(i))
        assert seg.end == pytest.approx(float(i) + 1.0)


def test_execute_renders_at_vertical_resolution(tmp_path: Path):
    media = FakeMediaProcessor()
    use_case = _make_use_case(media=media)
    image_path = _make_image(tmp_path)
    request = GenerateMicroVideoRequest(image_path=image_path, text="Hola.", output_dir=tmp_path / "out")

    use_case.execute(request)

    assert media.render_calls[0]["width"] == 1080
    assert media.render_calls[0]["height"] == 1920


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
