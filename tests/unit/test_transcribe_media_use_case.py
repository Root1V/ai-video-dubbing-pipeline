"""Tests de TranscribeMediaUseCase usando fakes en memoria (mismo patron que
test_translate_video_use_case.py): al depender solo de Protocols, no hace
falta ffmpeg ni un modelo de STT real."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_translator.application.use_cases.transcribe_media import TranscribeMediaUseCase
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import TranscribeMediaRequest, TranscriptSegment


class FakeMediaProcessor:
    def get_duration_seconds(self, media_path: Path) -> float:
        return 5.0

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        output_wav.write_bytes(b"fake-wav")
        return output_wav

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        raise NotImplementedError("no usado por TranscribeMediaUseCase")

    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        raise NotImplementedError("no usado por TranscribeMediaUseCase")

    def attach_soft_subtitles(self, video_path: Path, srt_path: Path, output_path: Path, lang_code: str = "spa") -> Path:
        raise NotImplementedError("no usado por TranscribeMediaUseCase")

    def replace_audio_track(
        self, video_path: Path, new_audio_path: Path, output_path: Path, keep_original_as_secondary: bool = True
    ) -> Path:
        raise NotImplementedError("no usado por TranscribeMediaUseCase")


class FakeTranscriber:
    def transcribe(self, audio_path: Path, language_hint=None):
        return [
            TranscriptSegment(id=0, start=0.0, end=2.0, text="Hello there."),
            TranscriptSegment(id=1, start=2.0, end=5.0, text="This is a test."),
        ]


class EmptyTranscriber:
    def transcribe(self, audio_path: Path, language_hint=None):
        return []


class FakeSubtitleWriter:
    def __init__(self):
        self.writes = []

    def write(self, segments, output_path, use_translation):
        self.writes.append((output_path, use_translation, list(segments)))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("srt content", encoding="utf-8")
        return output_path


class FakeSummarizer:
    def __init__(self):
        self.calls: list[str] = []

    def summarize(self, text: str) -> str:
        self.calls.append(text)
        return f"summary of: {text[:20]}"


@pytest.fixture()
def media_file(tmp_path: Path) -> Path:
    p = tmp_path / "input.mp4"
    p.write_bytes(b"fake-mp4")
    return p


def _make_use_case(transcriber=None, summarizer=None):
    return TranscribeMediaUseCase(
        media_processor=FakeMediaProcessor(),
        transcriber=transcriber or FakeTranscriber(),
        subtitle_writer=FakeSubtitleWriter(),
        summarizer=summarizer,
    )


def test_execute_writes_transcript_srt_and_text(tmp_path: Path, media_file: Path):
    use_case = _make_use_case()
    request = TranscribeMediaRequest(input_media=media_file, output_dir=tmp_path / "out")

    result = use_case.execute(request)

    assert result.transcript_srt_path == tmp_path / "out" / "transcript.srt"
    assert result.transcript_text_path == tmp_path / "out" / "transcript.txt"
    assert result.transcript_srt_path.exists()
    assert result.transcript_text_path.read_text(encoding="utf-8") == "Hello there.\nThis is a test."
    assert len(result.segments) == 2
    assert result.duration_seconds == 5.0
    assert result.timings["input"]["duration_seconds"] == 5.0


def test_execute_accepts_audio_only_input(tmp_path: Path):
    audio_file = tmp_path / "clip.mp3"
    audio_file.write_bytes(b"fake-mp3")
    use_case = _make_use_case()
    request = TranscribeMediaRequest(input_media=audio_file, output_dir=tmp_path / "out")

    result = use_case.execute(request)

    assert result.transcript_srt_path.exists()


def test_rejects_missing_file(tmp_path: Path):
    use_case = _make_use_case()
    request = TranscribeMediaRequest(input_media=tmp_path / "missing.mp4", output_dir=tmp_path / "out")

    with pytest.raises(InvalidVideoFileError):
        use_case.execute(request)


def test_rejects_unsupported_extension(tmp_path: Path):
    bad_file = tmp_path / "notes.txt"
    bad_file.write_bytes(b"x")
    use_case = _make_use_case()
    request = TranscribeMediaRequest(input_media=bad_file, output_dir=tmp_path / "out")

    with pytest.raises(InvalidVideoFileError):
        use_case.execute(request)


def test_raises_when_transcription_is_empty(tmp_path: Path, media_file: Path):
    use_case = _make_use_case(transcriber=EmptyTranscriber())
    request = TranscribeMediaRequest(input_media=media_file, output_dir=tmp_path / "out")

    with pytest.raises(VideoTranslatorError):
        use_case.execute(request)


def test_default_does_not_summarize(tmp_path: Path, media_file: Path):
    summarizer = FakeSummarizer()
    use_case = _make_use_case(summarizer=summarizer)
    request = TranscribeMediaRequest(input_media=media_file, output_dir=tmp_path / "out")

    result = use_case.execute(request)

    assert summarizer.calls == []
    assert result.summary_text is None
    assert not (tmp_path / "out" / "summary.txt").exists()


def test_include_summary_writes_summary_file(tmp_path: Path, media_file: Path):
    summarizer = FakeSummarizer()
    use_case = _make_use_case(summarizer=summarizer)
    request = TranscribeMediaRequest(
        input_media=media_file, output_dir=tmp_path / "out", include_summary=True
    )

    result = use_case.execute(request)

    # _chunk_text normaliza espacios en blanco (corta por palabra, no
    # preserva saltos de linea) -- para un texto que entra en un solo
    # fragmento el contenido es el mismo, solo cambia el whitespace.
    assert len(summarizer.calls) == 1
    assert summarizer.calls[0] == "Hello there. This is a test."
    summary_path = tmp_path / "out" / "summary.txt"
    assert summary_path.exists()
    assert result.summary_text == summary_path.read_text(encoding="utf-8")
    assert result.timings["outputs"]["summary_text_bytes"] > 0


def test_include_summary_chunks_long_transcripts(tmp_path: Path):
    long_segments_transcriber = type(
        "LongTranscriber",
        (),
        {
            "transcribe": lambda self, audio_path, language_hint=None: [
                TranscriptSegment(id=0, start=0.0, end=1.0, text="word " * 20),
                TranscriptSegment(id=1, start=1.0, end=2.0, text="word " * 20),
            ]
        },
    )()
    audio_file = tmp_path / "clip.mp3"
    audio_file.write_bytes(b"fake-mp3")
    summarizer = FakeSummarizer()
    use_case = _make_use_case(transcriber=long_segments_transcriber, summarizer=summarizer)
    request = TranscribeMediaRequest(
        input_media=audio_file, output_dir=tmp_path / "out", include_summary=True
    )

    # chunk_chars chico a proposito para forzar el camino map-reduce (2
    # fragmentos + 1 resumen final = 3 llamadas) sin necesitar un texto real
    # de miles de caracteres en el test.
    import video_translator.application.use_cases.transcribe_media as transcribe_media_module

    original_chunk_chars = transcribe_media_module._SUMMARY_CHUNK_CHARS
    transcribe_media_module._SUMMARY_CHUNK_CHARS = 50
    try:
        use_case.execute(request)
    finally:
        transcribe_media_module._SUMMARY_CHUNK_CHARS = original_chunk_chars

    # Con chunk_chars=50 el texto (40 palabras) se parte en varios
    # fragmentos -- no importa el numero exacto de fragmentos, lo que
    # importa es que hubo mas de un llamado (se tomo el camino map-reduce)
    # y que el ULTIMO llamado resume los resumenes parciales, no texto
    # crudo (confirma el paso de reduce final).
    assert len(summarizer.calls) > 1
    assert "summary of:" in summarizer.calls[-1]


def test_include_summary_without_summarizer_raises(tmp_path: Path, media_file: Path):
    use_case = _make_use_case(summarizer=None)
    request = TranscribeMediaRequest(
        input_media=media_file, output_dir=tmp_path / "out", include_summary=True
    )

    with pytest.raises(VideoTranslatorError):
        use_case.execute(request)
