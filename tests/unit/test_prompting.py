from __future__ import annotations

import pytest

from video_translator.domain.exceptions import TranslationError
from video_translator.domain.models import TranscriptSegment, TranslationContext
from video_translator.infrastructure.translation.prompting import (
    build_system_prompt,
    build_user_prompt,
    parse_numbered_lines,
)


def test_system_prompt_includes_context_and_glossary():
    ctx = TranslationContext(
        prompt="Video de cocina.",
        glossary={"whisk": "batidor"},
        tone="informal",
    )
    prompt = build_system_prompt(ctx)
    assert "Video de cocina." in prompt
    assert '"whisk" -> "batidor"' in prompt
    assert "informal" in prompt


def test_user_prompt_numbers_segments_and_includes_history():
    segments = [
        TranscriptSegment(id=0, start=0, end=1, text="Hello"),
        TranscriptSegment(id=1, start=1, end=2, text="World"),
    ]
    prompt = build_user_prompt(segments, rolling_history=["Hola previo"])
    assert "1. Hello" in prompt
    assert "2. World" in prompt
    assert "Hola previo" in prompt


def test_user_prompt_includes_speaker_and_gender_tags():
    segments = [
        TranscriptSegment(id=0, start=0, end=1, text="Hello", speaker_id="SPEAKER_00"),
        TranscriptSegment(id=1, start=1, end=2, text="Hi there", speaker_id="SPEAKER_01"),
    ]
    prompt = build_user_prompt(
        segments, rolling_history=[], speaker_genders={"SPEAKER_00": "male", "SPEAKER_01": "female"}
    )
    assert "[Hablante SPEAKER_00 - voz masculina] Hello" in prompt
    assert "[Hablante SPEAKER_01 - voz femenina] Hi there" in prompt


def test_system_prompt_lists_speaker_genders():
    ctx = TranslationContext(speaker_genders={"SPEAKER_00": "male"})
    prompt = build_system_prompt(ctx)
    assert "SPEAKER_00" in prompt
    assert "voz masculina" in prompt


def test_parse_numbered_lines_happy_path():
    raw = "1. Hola\n2. Mundo\n"
    assert parse_numbered_lines(raw, expected=2) == ["Hola", "Mundo"]


def test_parse_numbered_lines_raises_on_mismatch():
    raw = "1. Hola\n"
    with pytest.raises(TranslationError):
        parse_numbered_lines(raw, expected=2)
