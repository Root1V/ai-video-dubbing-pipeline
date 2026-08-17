from __future__ import annotations

from pathlib import Path

from video_translator.domain.models import TranslatedSegment
from video_translator.infrastructure.subtitles.srt_writer import SrtSubtitleWriter


def test_format_timestamp_basic():
    writer = SrtSubtitleWriter()
    assert writer._format_timestamp(0) == "00:00:00,000"
    assert writer._format_timestamp(61.5) == "00:01:01,500"
    assert writer._format_timestamp(3661.234) == "01:01:01,234"


def test_write_produces_valid_srt(tmp_path: Path):
    segments = [
        TranslatedSegment(id=0, start=0.0, end=1.5, source_text="Hi", translated_text="Hola"),
        TranslatedSegment(id=1, start=1.5, end=3.0, source_text="Bye", translated_text="Adios"),
    ]
    out = tmp_path / "out.srt"
    writer = SrtSubtitleWriter()
    writer.write(segments, out, use_translation=True)

    content = out.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,500\nHola" in content
    assert "2\n00:00:01,500 --> 00:00:03,000\nAdios" in content


def test_write_can_use_source_language(tmp_path: Path):
    segments = [TranslatedSegment(id=0, start=0.0, end=1.0, source_text="Hi", translated_text="Hola")]
    out = tmp_path / "out.en.srt"
    SrtSubtitleWriter().write(segments, out, use_translation=False)
    assert "Hi" in out.read_text(encoding="utf-8")
