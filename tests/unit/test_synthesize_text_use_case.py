"""Tests de SynthesizeTextUseCase usando fakes en memoria (mismo patron que
test_translate_video_use_case.py y test_transcribe_media_use_case.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_translator.application.use_cases.synthesize_text import SynthesizeTextUseCase
from video_translator.application.use_cases.text_chunking import split_into_chunks
from video_translator.domain.exceptions import VideoTranslatorError
from video_translator.domain.models import SynthesizeTextRequest


class FakeMediaProcessor:
    """Solo implementa get_duration_seconds -- lo unico que
    SynthesizeTextUseCase necesita de MediaProcessor. Devuelve una duracion
    fija por caracter para que el orden/timing de los segmentos sea
    verificable en los tests."""

    def get_duration_seconds(self, media_path: Path) -> float:
        return 1.0

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def attach_soft_subtitles(self, video_path: Path, srt_path: Path, output_path: Path, lang_code: str = "spa") -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def clean_music_track(self, input_path: Path, output_wav: Path) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def replace_audio_track(
        self, video_path: Path, new_audio_path: Path, output_path: Path, keep_original_as_secondary: bool = True
    ) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def render_image_video(
        self, image_path: Path, audio_path: Path, output_path: Path, duration_seconds: float,
        width: int = 1080, height: int = 1920,
    ) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def render_ass_captions(self, video_path: Path, ass_path: Path, output_path: Path) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def fit_audio_to_duration(self, audio_path: Path, target_seconds: float) -> bool:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")

    def mix_background_music(
        self, narration_path: Path, music_path: Path, output_path: Path,
        duration_seconds: float, music_volume: float = 0.12,
    ) -> Path:
        raise NotImplementedError("no usado por SynthesizeTextUseCase")


class FakeSpeechSynthesizer:
    def __init__(self):
        self.calls: list[dict] = []
        self.concatenated: list[tuple] = []

    def synthesize_segment(self, text, output_path, target_duration_seconds, speaker_reference_wav=None, language="es"):
        self.calls.append(
            {
                "text": text,
                "target_duration_seconds": target_duration_seconds,
                "speaker_reference_wav": speaker_reference_wav,
                "language": language,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-wav")
        return output_path

    def concatenate_segments(self, segment_audio_paths, total_duration, output_path):
        self.concatenated.append((list(segment_audio_paths), total_duration))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-concatenated-wav")
        return output_path


DEFAULT_VOICE = Path("/fake/default_voice.wav")


def _make_use_case(synthesizer=None, max_chunk_chars=500):
    return SynthesizeTextUseCase(
        speech_synthesizer=synthesizer or FakeSpeechSynthesizer(),
        media_processor=FakeMediaProcessor(),
        default_speaker_reference_wav=DEFAULT_VOICE,
        max_chunk_chars=max_chunk_chars,
    )


def test_execute_uses_default_voice_when_none_provided(tmp_path: Path):
    synthesizer = FakeSpeechSynthesizer()
    use_case = _make_use_case(synthesizer)
    request = SynthesizeTextRequest(text="Hola mundo.", output_dir=tmp_path / "out")

    result = use_case.execute(request)

    assert result.audio_path == tmp_path / "out" / "speech.wav"
    assert result.audio_path.exists()
    assert synthesizer.calls[0]["speaker_reference_wav"] == DEFAULT_VOICE
    assert synthesizer.calls[0]["target_duration_seconds"] == 0.0


def test_execute_uses_own_speaker_reference_when_provided(tmp_path: Path):
    synthesizer = FakeSpeechSynthesizer()
    use_case = _make_use_case(synthesizer)
    own_voice = tmp_path / "my_voice.wav"
    request = SynthesizeTextRequest(
        text="Hola mundo.", output_dir=tmp_path / "out", speaker_reference_wav=own_voice
    )

    use_case.execute(request)

    assert synthesizer.calls[0]["speaker_reference_wav"] == own_voice


def test_execute_passes_language(tmp_path: Path):
    synthesizer = FakeSpeechSynthesizer()
    use_case = _make_use_case(synthesizer)
    request = SynthesizeTextRequest(text="Hello.", output_dir=tmp_path / "out", language="en")

    use_case.execute(request)

    assert synthesizer.calls[0]["language"] == "en"


def test_execute_splits_long_text_into_multiple_chunks_and_concatenates(tmp_path: Path):
    synthesizer = FakeSpeechSynthesizer()
    use_case = _make_use_case(synthesizer, max_chunk_chars=20)
    long_text = "Primera oracion corta. Segunda oracion tambien corta. Tercera oracion mas."
    request = SynthesizeTextRequest(text=long_text, output_dir=tmp_path / "out")

    result = use_case.execute(request)

    assert len(synthesizer.calls) > 1
    assert len(synthesizer.concatenated) == 1
    segments, total_duration = synthesizer.concatenated[0]
    # Cada segmento dura 1.0s (FakeMediaProcessor); deben quedar en fila sin huecos.
    for i, (start, _path, max_duration) in enumerate(segments):
        assert start == pytest.approx(float(i))
        assert max_duration == pytest.approx(1.0)
    assert total_duration == pytest.approx(float(len(segments)))
    assert result.duration_seconds == pytest.approx(float(len(segments)))


def test_execute_rejects_empty_text(tmp_path: Path):
    use_case = _make_use_case()
    request = SynthesizeTextRequest(text="   ", output_dir=tmp_path / "out")

    with pytest.raises(VideoTranslatorError):
        use_case.execute(request)


def test_split_into_chunks_groups_sentences_greedily():
    text = "Uno. Dos. Tres. Cuatro."
    chunks = split_into_chunks(text, max_chars=8)

    assert chunks == ["Uno.", "Dos.", "Tres.", "Cuatro."]


def test_split_into_chunks_returns_whole_text_when_it_fits():
    chunks = split_into_chunks("Una sola oracion corta.", max_chars=500)

    assert chunks == ["Una sola oracion corta."]
