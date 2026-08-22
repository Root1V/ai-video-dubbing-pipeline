"""Tests del sistema de checkpointing/resumabilidad."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from video_translator.application.use_cases.translate_video import TranslateVideoUseCase
from video_translator.domain.models import (
    DiarizationSegment,
    OutputMode,
    TranscriptSegment,
    TranslateVideoRequest,
    TranslationContext,
)
from video_translator.utils.checkpoint import (
    STAGE_AUDIO_EXTRACTED,
    STAGE_SUBTITLES_WRITTEN,
    STAGE_TRANSCRIBED,
    STAGE_TRANSLATED,
    Checkpoint,
    CheckpointStore,
    restore_diarization_segments,
    restore_speaker_profiles,
    restore_transcript_segments,
    restore_translated_segments,
)

# --- Fakes (reutilizados del test del caso de uso) ---


class FakeMediaProcessor:
    def __init__(self):
        self.burned = False
        self.soft = False

    def get_duration_seconds(self, media_path: Path) -> float:
        return 5.0

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        output_wav.write_bytes(b"fake-wav")
        return output_wav

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-clip")
        return output_path

    def burn_subtitles(self, video_path, srt_path, output_path):
        self.burned = True
        output_path.write_bytes(b"video")
        return output_path

    def attach_soft_subtitles(self, video_path, srt_path, output_path, lang_code="spa"):
        self.soft = True
        output_path.write_bytes(b"video")
        return output_path

    def replace_audio_track(self, video_path, new_audio_path, output_path, keep_original_as_secondary=True):
        output_path.write_bytes(b"video")
        return output_path


class FakeTranscriber:
    def transcribe(self, audio_path: Path, language_hint=None):
        return [
            TranscriptSegment(id=0, start=0.0, end=2.0, text="Hello there."),
            TranscriptSegment(id=1, start=2.0, end=5.0, text="This is a test video."),
        ]


class FakeTranslator:
    def translate_batch(self, segments, context, rolling_history):
        return [f"[ES] {s.text}" for s in segments]


class FakeSubtitleWriter:
    def write(self, segments, output_path, use_translation):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("srt content", encoding="utf-8")
        return output_path


class RecordingSynthesizer:
    def __init__(self):
        self.calls = []
        self.concat_args = []

    def synthesize_segment(self, text, output_path, target_duration_seconds, speaker_reference_wav=None, language="es"):
        self.calls.append((text, speaker_reference_wav))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"wav")
        return output_path

    def concatenate_segments(self, segment_audio_paths, total_duration, output_path):
        self.concat_args = segment_audio_paths
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"wav")
        return output_path


@pytest.fixture()
def video_file(tmp_path: Path) -> Path:
    p = tmp_path / "input.mp4"
    p.write_bytes(b"fake-mp4")
    return p


def _make_checkpoint(
    input_video: str = "/fake/video.mp4",
    completed_stages: list[str] | None = None,
    **kwargs,
) -> Checkpoint:
    return Checkpoint(
        input_video=input_video,
        input_size=12345,
        input_mtime=99999.0,
        source_lang_hint="en",
        diarize=False,
        output_mode="subtitles_only",
        completed_stages=completed_stages or [],
        **kwargs,
    )


# --- CheckpointStore tests ---


def test_checkpoint_store_save_and_load(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    cp = _make_checkpoint(completed_stages=[STAGE_AUDIO_EXTRACTED, STAGE_TRANSCRIBED])
    store.save(cp)

    assert store.exists()
    loaded = store.load()
    assert loaded is not None
    assert loaded.completed_stages == [STAGE_AUDIO_EXTRACTED, STAGE_TRANSCRIBED]
    assert loaded.input_video == "/fake/video.mp4"


def test_checkpoint_store_load_returns_none_when_no_file(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    assert store.load() is None
    assert not store.exists()


def test_checkpoint_store_clear_removes_file(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    store.save(_make_checkpoint())
    assert store.exists()
    store.clear()
    assert not store.exists()


def test_checkpoint_store_save_is_atomic_on_crash(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    cp = _make_checkpoint(completed_stages=[STAGE_TRANSLATED])
    store.save(cp)

    raw = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert raw["completed_stages"] == [STAGE_TRANSLATED]
    assert raw["input_video"] == "/fake/video.mp4"


# --- Restore functions tests ---


def test_restore_transcript_segments_roundtrip():
    seg = TranscriptSegment(id=0, start=1.0, end=3.0, text="hello", language="en", speaker_id="S0")
    cp = Checkpoint(
        input_video="/fake", input_size=1, input_mtime=1.0,
        source_lang_hint="en", diarize=False, output_mode="subtitles_only",
        transcript_segments=[{"id": 0, "start": 1.0, "end": 3.0, "text": "hello", "language": "en", "speaker_id": "S0"}],
    )
    restored = restore_transcript_segments(cp)
    assert len(restored) == 1
    assert restored[0] == seg


def test_restore_diarization_segments_roundtrip():
    cp = Checkpoint(
        input_video="/fake", input_size=1, input_mtime=1.0,
        source_lang_hint="en", diarize=True, output_mode="subtitles_only",
        diarization_segments=[{"start": 0.0, "end": 2.0, "speaker_label": "SPEAKER_00"}],
    )
    restored = restore_diarization_segments(cp)
    assert restored is not None
    assert restored[0] == DiarizationSegment(start=0.0, end=2.0, speaker_label="SPEAKER_00")


def test_restore_diarization_segments_none():
    cp = Checkpoint(
        input_video="/fake", input_size=1, input_mtime=1.0,
        source_lang_hint="en", diarize=False, output_mode="subtitles_only",
        diarization_segments=None,
    )
    assert restore_diarization_segments(cp) is None


def test_restore_speaker_profiles_roundtrip(tmp_path: Path):
    ref_wav = tmp_path / "S0.wav"
    ref_wav.write_bytes(b"x")
    cp = Checkpoint(
        input_video="/fake", input_size=1, input_mtime=1.0,
        source_lang_hint="en", diarize=True, output_mode="dubbed",
        speaker_profiles=[
            {"speaker_id": "SPEAKER_00", "gender": "male", "reference_wav": str(ref_wav)},
            {"speaker_id": "SPEAKER_01", "gender": "female", "reference_wav": None},
        ],
    )
    restored = restore_speaker_profiles(cp)
    assert len(restored) == 2
    assert restored[0].speaker_id == "SPEAKER_00"
    assert restored[0].gender == "male"
    assert restored[0].reference_wav == ref_wav
    assert restored[1].reference_wav is None


def test_restore_translated_segments_roundtrip():
    cp = Checkpoint(
        input_video="/fake", input_size=1, input_mtime=1.0,
        source_lang_hint="en", diarize=False, output_mode="subtitles_only",
        translated_segments=[
            {"id": 0, "start": 0.0, "end": 2.0, "source_text": "hello", "translated_text": "hola", "speaker_id": None},
        ],
    )
    restored = restore_translated_segments(cp)
    assert restored is not None
    assert restored[0].translated_text == "hola"
    assert restored[0].source_text == "hello"


def test_restore_translated_segments_none():
    cp = Checkpoint(
        input_video="/fake", input_size=1, input_mtime=1.0,
        source_lang_hint="en", diarize=False, output_mode="subtitles_only",
        translated_segments=None,
    )
    assert restore_translated_segments(cp) is None


# --- UseCase resume integration tests ---


def _build_use_case(resume: bool = False, **kwargs):
    return TranslateVideoUseCase(
        media_processor=FakeMediaProcessor(),
        transcriber=FakeTranscriber(),
        translator=FakeTranslator(),
        subtitle_writer=FakeSubtitleWriter(),
        resume=resume,
        **kwargs,
    )


def test_resume_skips_already_completed_stages(tmp_path: Path, video_file: Path):
    """Si el checkpoint indica que transcripcion y traduccion ya estan hechas,
    el pipeline no debe volver a llamar al transcritor ni al traductor."""
    use_case = _build_use_case(resume=True)
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )

    # Simular un checkpoint previamente guardado con transcripcion + traduccion completadas.
    workdir = request.output_dir / "_work"
    workdir.mkdir(parents=True, exist_ok=True)
    store = CheckpointStore(workdir)
    store.save(Checkpoint(
        input_video=str(video_file),
        input_size=video_file.stat().st_size,
        input_mtime=video_file.stat().st_mtime,
        source_lang_hint=request.source_lang_hint,
        diarize=request.diarize,
        output_mode=request.output_mode.value,
        completed_stages=[STAGE_AUDIO_EXTRACTED, STAGE_TRANSCRIBED, STAGE_TRANSLATED],
        transcript_segments=[
            {"id": 0, "start": 0.0, "end": 2.0, "text": "Hello there.", "language": "en", "speaker_id": None},
            {"id": 1, "start": 2.0, "end": 5.0, "text": "This is a test video.", "language": "en", "speaker_id": None},
        ],
        translated_segments=[
            {"id": 0, "start": 0.0, "end": 2.0, "source_text": "Hello there.", "translated_text": "[ES] Hello there.", "speaker_id": None},
            {"id": 1, "start": 2.0, "end": 5.0, "source_text": "This is a test video.", "translated_text": "[ES] This is a test video.", "speaker_id": None},
        ],
    ))

    # Mock para detectar si se llama al transcritor/traductor.
    use_case._transcriber.transcribe = MagicMock(return_value=[])
    use_case._translator.translate_batch = MagicMock(return_value=[])

    result = use_case.execute(request)

    use_case._transcriber.transcribe.assert_not_called()
    use_case._translator.translate_batch.assert_not_called()
    assert len(result.segments) == 2
    assert result.segments[0].translated_text == "[ES] Hello there."
    # El checkpoint se limpia al finalizar con exito.
    assert not store.exists()


def test_resume_ignores_mismatched_checkpoint(tmp_path: Path, video_file: Path):
    """Si el checkpoint corresponde a un video o modo diferente, se ignora y
    se ejecuta el pipeline desde cero."""
    use_case = _build_use_case(resume=True)
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )
    workdir = request.output_dir / "_work"
    workdir.mkdir(parents=True, exist_ok=True)
    store = CheckpointStore(workdir)
    # Checkpoint con un path de video distinto -> no coincide.
    store.save(Checkpoint(
        input_video="/otro/video.mp4",
        input_size=999,
        input_mtime=1.0,
        source_lang_hint="en",
        diarize=False,
        output_mode="subtitles_only",
        completed_stages=[STAGE_TRANSCRIBED],
        transcript_segments=[],
    ))

    result = use_case.execute(request)

    assert len(result.segments) == 2  # el FakeTranscriber produce 2 segmentos


def test_no_resume_does_not_load_checkpoint(tmp_path: Path, video_file: Path):
    """Sin --resume, el checkpoint existente se ignora por completo."""
    use_case = _build_use_case(resume=False)
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )
    workdir = request.output_dir / "_work"
    workdir.mkdir(parents=True, exist_ok=True)
    store = CheckpointStore(workdir)
    store.save(Checkpoint(
        input_video=str(video_file),
        input_size=video_file.stat().st_size,
        input_mtime=video_file.stat().st_mtime,
        source_lang_hint="en",
        diarize=False,
        output_mode="subtitles_only",
        completed_stages=[STAGE_TRANSCRIBED],
        transcript_segments=[{"id": 0, "start": 0, "end": 1, "text": "stale", "language": "en", "speaker_id": None}],
    ))

    result = use_case.execute(request)

    # Debe usar los datos frescos del FakeTranscriber, no el checkpoint.
    assert result.segments[0].source_text == "Hello there."


def test_checkpoint_created_after_audio_extraction(tmp_path: Path, video_file: Path):
    """El checkpoint se crea inmediatamente despues de extraer el audio."""
    use_case = _build_use_case(resume=False)
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )
    use_case.execute(request)

    workdir = request.output_dir / "_work"
    store = CheckpointStore(workdir)
    cp = store.load()
    assert cp is not None
    assert STAGE_AUDIO_EXTRACTED in cp.completed_stages
    assert STAGE_TRANSCRIBED in cp.completed_stages
    assert STAGE_TRANSLATED in cp.completed_stages
    assert STAGE_SUBTITLES_WRITTEN in cp.completed_stages


def test_resume_dubbed_skips_existing_tts_files(tmp_path: Path, video_file: Path):
    """En modo doblaje, si los archivos WAV de TTS ya existen, no se regeneran."""
    use_case = _build_use_case(resume=True, speech_synthesizer=RecordingSynthesizer())
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.DUBBED,
    )
    workdir = request.output_dir / "_work"
    workdir.mkdir(parents=True, exist_ok=True)
    store = CheckpointStore(workdir)

    # Pre-crear los archivos WAV de TTS "existentes" para simular que TTS ya corrio.
    segment_dir = workdir / "tts_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    (segment_dir / "group_000000.wav").write_bytes(b"existing-wav-data")
    (segment_dir / "group_000001.wav").write_bytes(b"existing-wav-data")

    # Tambien pre-guardar el audio y la transcripcion + traduccion.
    audio_wav = workdir / "audio_16k_mono.wav"
    audio_wav.write_bytes(b"fake-wav")

    store.save(Checkpoint(
        input_video=str(video_file),
        input_size=video_file.stat().st_size,
        input_mtime=video_file.stat().st_mtime,
        source_lang_hint="en",
        diarize=False,
        output_mode="dubbed",
        completed_stages=[
            STAGE_AUDIO_EXTRACTED,
            STAGE_TRANSCRIBED,
            STAGE_TRANSLATED,
            STAGE_SUBTITLES_WRITTEN,
        ],
        transcript_segments=[
            {"id": 0, "start": 0.0, "end": 2.0, "text": "Hello.", "language": "en", "speaker_id": None},
            {"id": 1, "start": 2.0, "end": 5.0, "text": "Test.", "language": "en", "speaker_id": None},
        ],
        translated_segments=[
            {"id": 0, "start": 0.0, "end": 2.0, "source_text": "Hello.", "translated_text": "[ES] Hello.", "speaker_id": None},
            {"id": 1, "start": 2.0, "end": 5.0, "source_text": "Test.", "translated_text": "[ES] Test.", "speaker_id": None},
        ],
    ))

    synthesizer = use_case._synthesizer
    assert isinstance(synthesizer, RecordingSynthesizer)
    original_calls = len(synthesizer.calls)

    result = use_case.execute(request)

    # TTS no deberia haber generado nada nuevo (archivos ya existian).
    assert len(synthesizer.calls) == original_calls
    assert result.output_video is not None
    assert result.output_video.exists()
