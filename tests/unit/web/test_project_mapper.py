"""Tests de project_mapper: Project (fila de BD) -> TranslateVideoRequest/use case.

No requiere GPU/modelos reales: se mockea `build_translate_video_use_case`
(container.py) para verificar solo el mapeo de datos, que es la
responsabilidad real de este modulo.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from video_translator.domain.models import OutputMode
from video_translator.web.db.models import Project, ProjectStatus, ServiceType, SourceType
from video_translator.web.services import project_mapper


def _make_project(tmp_path: Path, **config_overrides: object) -> Project:
    config = {
        "context_prompt": "Video de prueba",
        "tone": "formal",
        "glossary": {"foo": "bar"},
        "source_lang": "en",
        "target_lang": "es",
        "diarize": False,
        "min_speakers": None,
        "max_speakers": None,
        **config_overrides,
    }
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Proyecto de prueba",
        service_type=ServiceType.DUBBING,
        source_type=SourceType.UPLOAD,
        input_video_path=str(tmp_path / "input.mp4"),
        output_dir=str(tmp_path / "output"),
        output_mode=OutputMode.DUBBED.value,
        config=config,
        status=ProjectStatus.QUEUED,
    )


def test_build_use_case_and_request_maps_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _make_project(tmp_path, diarize=True, min_speakers=2, max_speakers=3)

    fake_use_case = MagicMock()
    build_mock = MagicMock(return_value=fake_use_case)
    monkeypatch.setattr(project_mapper, "build_translate_video_use_case", build_mock)

    use_case, request = project_mapper.build_use_case_and_request(project)

    assert use_case is fake_use_case
    assert request.input_video == Path(project.input_video_path)
    assert request.output_dir == Path(project.output_dir)
    assert request.output_dir.is_dir()  # se crea, igual que hace cli.py
    assert request.output_mode == OutputMode.DUBBED
    assert request.diarize is True
    assert request.min_speakers == 2
    assert request.max_speakers == 3
    assert request.context.prompt == "Video de prueba"
    assert request.context.tone == "formal"
    assert request.context.glossary == {"foo": "bar"}
    assert request.context.source_lang == "en"
    assert request.context.target_lang == "es"

    build_mock.assert_called_once()
    _, kwargs = build_mock.call_args
    assert kwargs["enable_dubbing"] is True
    assert kwargs["enable_diarization"] is True
    assert kwargs["resume"] is False


def test_build_use_case_and_request_subtitles_only_disables_dubbing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_project(tmp_path)
    project.output_mode = OutputMode.SUBTITLES_ONLY.value

    build_mock = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(project_mapper, "build_translate_video_use_case", build_mock)

    _, request = project_mapper.build_use_case_and_request(project)

    assert request.output_mode == OutputMode.SUBTITLES_ONLY
    _, kwargs = build_mock.call_args
    assert kwargs["enable_dubbing"] is False


def test_build_use_case_and_request_passes_resume_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_project(tmp_path)
    build_mock = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(project_mapper, "build_translate_video_use_case", build_mock)

    project_mapper.build_use_case_and_request(project, resume=True)

    _, kwargs = build_mock.call_args
    assert kwargs["resume"] is True


def test_build_use_case_and_request_applies_tts_workers_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_project(tmp_path, tts_workers=2)
    build_mock = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(project_mapper, "build_translate_video_use_case", build_mock)

    project_mapper.build_use_case_and_request(project)

    (settings_arg, *_rest), _ = build_mock.call_args
    assert settings_arg.tts_parallel_workers == 2


def _make_transcription_project(tmp_path: Path, **config_overrides: object) -> Project:
    config = {"source_lang": "en", **config_overrides}
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Proyecto de transcripcion",
        service_type=ServiceType.TRANSCRIPTION,
        source_type=SourceType.UPLOAD,
        input_video_path=str(tmp_path / "input.mp3"),
        output_dir=str(tmp_path / "output"),
        output_mode=OutputMode.SUBTITLES_ONLY.value,
        config=config,
        status=ProjectStatus.QUEUED,
    )


def test_build_transcribe_use_case_and_request_maps_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_transcription_project(tmp_path, source_lang="fr")

    fake_use_case = MagicMock()
    build_mock = MagicMock(return_value=fake_use_case)
    monkeypatch.setattr(project_mapper, "build_transcribe_media_use_case", build_mock)

    use_case, request = project_mapper.build_transcribe_use_case_and_request(project)

    assert use_case is fake_use_case
    assert request.input_media == Path(project.input_video_path)
    assert request.output_dir == Path(project.output_dir)
    assert request.output_dir.is_dir()
    assert request.source_lang_hint == "fr"
    build_mock.assert_called_once()


def test_build_transcribe_use_case_and_request_empty_source_lang_means_auto_detect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_transcription_project(tmp_path, source_lang="")
    monkeypatch.setattr(project_mapper, "build_transcribe_media_use_case", MagicMock(return_value=MagicMock()))

    _, request = project_mapper.build_transcribe_use_case_and_request(project)

    assert request.source_lang_hint is None


def _make_tts_project(tmp_path: Path, text: str = "Hola mundo.", **config_overrides: object) -> Project:
    text_path = tmp_path / "input.txt"
    text_path.write_text(text, encoding="utf-8")
    config = {"target_lang": "es", **config_overrides}
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Proyecto de TTS",
        service_type=ServiceType.TTS,
        source_type=SourceType.UPLOAD,
        input_video_path=str(text_path),
        output_dir=str(tmp_path / "output"),
        output_mode=OutputMode.SUBTITLES_ONLY.value,
        config=config,
        status=ProjectStatus.QUEUED,
    )


def test_build_synthesize_use_case_and_request_reads_text_and_maps_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_tts_project(tmp_path, text="Hola mundo.", target_lang="en")

    fake_use_case = MagicMock()
    build_mock = MagicMock(return_value=fake_use_case)
    monkeypatch.setattr(project_mapper, "build_synthesize_text_use_case", build_mock)

    use_case, request = project_mapper.build_synthesize_use_case_and_request(project)

    assert use_case is fake_use_case
    assert request.text == "Hola mundo."
    assert request.output_dir == Path(project.output_dir)
    assert request.output_dir.is_dir()
    assert request.language == "en"
    assert request.speaker_reference_wav is None
    build_mock.assert_called_once()


def test_build_synthesize_use_case_and_request_maps_speaker_reference_wav(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    voice_path = tmp_path / "voice.wav"
    project = _make_tts_project(tmp_path, speaker_reference_wav=str(voice_path))
    monkeypatch.setattr(project_mapper, "build_synthesize_text_use_case", MagicMock(return_value=MagicMock()))

    _, request = project_mapper.build_synthesize_use_case_and_request(project)

    assert request.speaker_reference_wav == voice_path
