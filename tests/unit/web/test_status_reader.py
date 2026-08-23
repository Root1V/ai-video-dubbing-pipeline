"""Tests de status_reader.read_project_status: disco (pipeline_timings.json)
vs. fallback a status de BD."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from video_translator.web.db.models import Project, ProjectStatus
from video_translator.web.services.status_reader import read_project_status


def _make_project(output_dir: Path, status: ProjectStatus = ProjectStatus.RUNNING) -> Project:
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Test project",
        service_type="dubbing",
        source_type="upload",
        input_video_path="/tmp/in.mp4",
        output_dir=str(output_dir),
        output_mode="dubbed",
        config={},
        status=status,
    )


def test_read_project_status_falls_back_to_db_when_file_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "missing", status=ProjectStatus.RUNNING)

    result = read_project_status(project)

    assert result["db_status"] == ProjectStatus.RUNNING
    assert result["run_id"] is None
    assert result["completed"] is None
    assert result["current_stage"] is None
    assert result["stages"] is None
    assert result["total_seconds"] is None
    assert result["realtime_factor"] is None
    assert result["warnings"] is None


def test_read_project_status_falls_back_to_db_when_completed(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "missing", status=ProjectStatus.COMPLETED)

    result = read_project_status(project)

    assert result["completed"] is True


def test_read_project_status_reads_pipeline_timings_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    fake_report = {
        "run_id": "abc123def456",
        "completed": False,
        "current_stage": {"name": "translation", "started_at": "2026-08-23T00:00:00+00:00"},
        "stages": [{"order": 1, "name": "transcription", "seconds": 12.3}],
        "total_seconds": 45.6,
        "realtime_factor": 1.5,
        "warnings": [{"source": "tts", "at": "2026-08-23T00:00:00+00:00"}],
    }
    (output_dir / "pipeline_timings.json").write_text(json.dumps(fake_report), encoding="utf-8")
    project = _make_project(output_dir, status=ProjectStatus.RUNNING)

    result = read_project_status(project)

    assert result["db_status"] == ProjectStatus.RUNNING
    assert result["run_id"] == "abc123def456"
    assert result["completed"] is False
    assert result["current_stage"] == fake_report["current_stage"]
    assert result["stages"] == fake_report["stages"]
    assert result["total_seconds"] == 45.6
    assert result["realtime_factor"] == 1.5
    assert result["warnings"] == fake_report["warnings"]


def test_read_project_status_falls_back_when_file_is_corrupt(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "pipeline_timings.json").write_text("{not valid json", encoding="utf-8")
    project = _make_project(output_dir, status=ProjectStatus.RUNNING)

    result = read_project_status(project)

    assert result["db_status"] == ProjectStatus.RUNNING
    assert result["run_id"] is None
    assert result["stages"] is None
