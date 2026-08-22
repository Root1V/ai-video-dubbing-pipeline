from __future__ import annotations

from pathlib import Path

from video_translator.utils.logging_config import configure_logging, get_logger


def test_logs_are_written_to_file_without_ansi_colors(tmp_path: Path):
    log_file = tmp_path / "logs" / "run.log"
    configure_logging(level="INFO", json_logs=False, log_file=log_file)

    log = get_logger("test.module")
    log.info("pipeline.test_event", foo="bar", num=3)

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "pipeline.test_event" in content
    assert "foo" in content and "bar" in content
    # Sin codigos de escape ANSI (el renderer de archivo va con colors=False).
    assert "\x1b[" not in content


def test_json_mode_writes_valid_json_lines(tmp_path: Path):
    import json

    log_file = tmp_path / "run.log"
    configure_logging(level="INFO", json_logs=True, log_file=log_file)

    log = get_logger("test.module")
    log.info("pipeline.json_event", value=42)

    lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    parsed = json.loads(lines[-1])
    assert parsed["event"] == "pipeline.json_event"
    assert parsed["value"] == 42


def test_configure_logging_without_log_file_does_not_raise(tmp_path: Path):
    # No deberia intentar crear ningun archivo si log_file es None.
    configure_logging(level="INFO", json_logs=False, log_file=None)
    log = get_logger("test.module")
    log.info("pipeline.console_only_event")  # no debe lanzar
