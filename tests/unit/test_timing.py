from __future__ import annotations

import json
import time
from pathlib import Path

from video_translator.utils.timing import PipelineTimings


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_stage_records_duration_and_metadata():
    t = PipelineTimings()
    with t.stage("fake_stage", num_items=3):
        time.sleep(0.01)
    data = t.as_dict()
    assert len(data["stages"]) == 1
    stage = data["stages"][0]
    assert stage["name"] == "fake_stage"
    assert stage["seconds"] >= 0.01
    assert stage["num_items"] == 3
    assert "percent_of_total" in stage


def test_record_adds_a_manually_measured_stage():
    t = PipelineTimings()
    t.record("manual_stage", 1.23, foo="bar")
    data = t.as_dict()
    assert data["stages"][0]["name"] == "manual_stage"
    assert data["stages"][0]["seconds"] == 1.23
    assert data["stages"][0]["foo"] == "bar"


def test_mark_concurrent_is_included_in_report():
    t = PipelineTimings()
    t.record("a", 1.0)
    t.record("b", 1.0)
    t.mark_concurrent(["a", "b"])
    data = t.as_dict()
    assert data["concurrent_stage_groups"] == [["a", "b"]]


def test_run_id_is_generated_when_not_provided():
    t = PipelineTimings()
    assert len(t.run_id) > 0


def test_run_id_can_be_provided_explicitly():
    t = PipelineTimings(run_id="fixed-id")
    assert t.run_id == "fixed-id"


def test_write_report_persists_valid_json(tmp_path: Path):
    t = PipelineTimings()
    t.record("stage_a", 2.0)
    report_path = tmp_path / "sub" / "pipeline_timings.json"
    t.write_report(report_path)

    assert report_path.exists()
    data = _read(report_path)
    assert data["stages"][0]["name"] == "stage_a"


def test_stages_have_incremental_order():
    t = PipelineTimings()
    with t.stage("first"):
        pass
    with t.stage("second"):
        pass
    t.record("third", 1.0)
    orders = [s["order"] for s in t.as_dict()["stages"]]
    names = [s["name"] for s in t.as_dict()["stages"]]
    assert orders == [1, 2, 3]
    assert names == ["first", "second", "third"]


def test_report_is_updated_after_each_stage(tmp_path: Path):
    report_path = tmp_path / "pipeline_timings.json"
    t = PipelineTimings(report_path=report_path)

    with t.stage("one"):
        pass
    # Sin llamar write_report: el snapshot incremental ya existe y tiene la etapa 1.
    partial = _read(report_path)
    assert [s["name"] for s in partial["stages"]] == ["one"]

    with t.stage("two"):
        pass
    updated = _read(report_path)
    assert [s["name"] for s in updated["stages"]] == ["one", "two"]
    assert [s["order"] for s in updated["stages"]] == [1, 2]


def test_current_stage_is_visible_while_running(tmp_path: Path):
    report_path = tmp_path / "pipeline_timings.json"
    t = PipelineTimings(report_path=report_path)
    with t.stage("long_running"):
        snapshot = _read(report_path)
    assert snapshot["current_stage"]["name"] == "long_running"
    assert "started_at" in snapshot["current_stage"]
    # Al salir de la etapa, current_stage desaparece.
    assert "current_stage" not in _read(report_path)


def test_stage_that_raises_is_not_recorded_as_completed(tmp_path: Path):
    report_path = tmp_path / "pipeline_timings.json"
    t = PipelineTimings(report_path=report_path)
    try:
        with t.stage("translation", num_segments=10):
            raise RuntimeError("llama-server no responde")
    except RuntimeError:
        pass

    data = t.as_dict()
    # No debe aparecer como una etapa "completed" -- nunca termino.
    assert data["stages"] == []
    # current_stage se deja tal cual (no se limpia), asi el reporte refleja
    # donde se interrumpio realmente en vez de mostrarla como exitosa.
    assert data["current_stage"]["name"] == "translation"
    on_disk = _read(report_path)
    assert on_disk["stages"] == []
    assert on_disk["current_stage"]["name"] == "translation"


def test_completed_flag_only_on_final_write(tmp_path: Path):
    report_path = tmp_path / "pipeline_timings.json"
    t = PipelineTimings(report_path=report_path)
    t.record("a", 1.0)
    assert _read(report_path)["completed"] is False
    t.write_report(report_path, final=True)
    assert _read(report_path)["completed"] is True


def test_stage_timestamps_are_recorded():
    t = PipelineTimings()
    with t.stage("ts"):
        pass
    stage = t.as_dict()["stages"][0]
    assert stage["started_at"] is not None
    assert stage["ended_at"] is not None
    assert stage["started_at"] <= stage["ended_at"]


def test_parallel_time_saved_is_computed():
    t = PipelineTimings()
    t.record("transcription", 10.0)
    t.record("diarization", 6.0)
    t.mark_concurrent(["transcription", "diarization"])
    # Se solapan: en vez de 16s de suma, costaron max(10, 6) = 10 -> 6s ahorrados.
    assert t.as_dict()["parallel_time_saved_seconds"] == 6.0


def test_adopt_previous_report_restores_real_durations(tmp_path: Path):
    previous = {
        "run_id": "old",
        "stages": [
            {"order": 1, "name": "audio_extraction", "seconds": 4.2, "status": "completed"},
            {"order": 2, "name": "transcription", "seconds": 1802.5,
             "started_at": "2026-08-20T10:00:00+00:00", "ended_at": "2026-08-20T10:30:02+00:00"},
            {"order": 3, "name": "diarization", "seconds": 1950.7},
        ],
    }
    prev_path = tmp_path / "pipeline_timings.json"
    prev_path.write_text(json.dumps(previous), encoding="utf-8")

    t = PipelineTimings(report_path=tmp_path / "out.json")
    t.mark_resumed()
    assert t.adopt_previous_report(prev_path) == 3

    # La corrida reanudada salta esas etapas...
    t.record_resumed("audio_extraction")
    t.record_resumed("transcription")
    t.record_resumed("diarization")

    stages = {s["name"]: s for s in t.as_dict()["stages"]}
    assert stages["transcription"]["seconds"] == 1802.5
    assert stages["transcription"]["status"] == "resumed"
    assert stages["transcription"]["started_at"] == "2026-08-20T10:00:00+00:00"
    assert stages["audio_extraction"]["seconds"] == 4.2
    assert stages["diarization"]["percent_of_total"] >= 0


def test_record_resumed_falls_back_to_zero_without_previous_data():
    t = PipelineTimings()  # sin adopt_previous_report
    t.record_resumed("translation", num_segments=10)
    stage = t.as_dict()["stages"][0]
    assert stage["seconds"] == 0.0
    assert stage["status"] == "resumed"
    assert stage["num_segments"] == 10


def test_adopt_previous_report_carries_concurrent_groups(tmp_path: Path):
    # En la corrida anterior transcription/diarization se solaparon; al
    # reanudar (donde ambas etapas se saltan) el reporte debe SEGUIR
    # reportando el ahorro de tiempo del paralelismo original.
    previous = {
        "run_id": "old",
        "concurrent_stage_groups": [["transcription", "diarization"]],
        "stages": [
            {"order": 1, "name": "transcription", "seconds": 10.0},
            {"order": 2, "name": "diarization", "seconds": 6.0},
        ],
    }
    prev_path = tmp_path / "pipeline_timings.json"
    prev_path.write_text(json.dumps(previous), encoding="utf-8")

    t = PipelineTimings(report_path=tmp_path / "out.json")
    t.adopt_previous_report(prev_path)
    t.record_resumed("transcription")
    t.record_resumed("diarization")

    report = t.as_dict()
    assert ["transcription", "diarization"] in report["concurrent_stage_groups"]
    assert report["parallel_time_saved_seconds"] == 6.0  # sum(10,6) - max(10,6) = 16-10


def test_percent_of_total_uses_work_sum_not_wall_time():
    # Con etapas resumed heredando duraciones grandes y poco tiempo de pared
    # propio, el % debe seguir siendo consistente contra la suma de trabajo.
    t = PipelineTimings()
    t.record("transcription", 200.0)
    t.record("translation", 30.0)
    stages = t.as_dict()["stages"]
    assert stages[0]["percent_of_total"] == 87.0  # 200/230
    assert stages[1]["percent_of_total"] == 13.0


def test_adopt_previous_report_survives_corrupt_file(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    t = PipelineTimings()
    assert t.adopt_previous_report(bad) == 0
    t.record_resumed("anything")


def test_run_ids_chain_accumulates_across_resumes(tmp_path: Path):
    prev_path = tmp_path / "pipeline_timings.json"
    prev_path.write_text(
        json.dumps(
            {
                "run_id": "run-old",
                "stages": [{"order": 1, "name": "transcription", "seconds": 5.0}],
            }
        ),
        encoding="utf-8",
    )

    first = PipelineTimings(run_id="run-mid", report_path=prev_path)
    first.adopt_previous_report(prev_path)
    assert first.as_dict()["run_ids"] == ["run-old", "run-mid"]
    # Simula que esta corrida intermedia dejo su propio reporte (ya con cadena).
    prev_path.write_text(json.dumps(first.as_dict()), encoding="utf-8")

    second = PipelineTimings(run_id="run-last", report_path=tmp_path / "out.json")
    second.adopt_previous_report(prev_path)
    report = second.as_dict()
    assert report["run_ids"] == ["run-old", "run-mid", "run-last"]
    assert report["run_id"] == "run-last"  # compatibilidad: el actual sigue en run_id


def test_reserved_keys_cannot_be_overridden_by_metadata():
    t = PipelineTimings()
    t.record("evil", 1.0, order=99, status="nope", percent_of_total=100.0)
    stage = t.as_dict()["stages"][0]
    assert stage["order"] == 1
    assert stage["seconds"] == 1.0
    assert stage["name"] == "evil"
    assert stage["status"] == "completed"


def test_top_level_summary_metrics(tmp_path: Path):
    t = PipelineTimings(report_path=tmp_path / "r.json")
    t.record("a", 2.0)
    t.record("b", 3.0)
    t.write_report(tmp_path / "r.json", final=True)
    data = _read(tmp_path / "r.json")
    assert data["num_stages"] == 2
    assert data["sum_of_stage_seconds"] == 5.0
    assert data["overhead_seconds"] >= 0
    assert data["resumed_run"] is False
    assert data["total_seconds"] >= 0
    assert "started_at" in data and "generated_at" in data


def test_input_and_realtime_factor(tmp_path: Path):
    report = tmp_path / "r.json"
    t = PipelineTimings(report_path=report)
    t.set_input("video/clip.mp4", duration_seconds=120.0)
    t.record("everything", 240.0)
    t.write_report(report, final=True)
    data = _read(report)
    assert data["input"]["video"] == "video/clip.mp4"
    assert data["input"]["duration_seconds"] == 120.0
    # El factor se deriva del tiempo real transcurrido (no de la suma de etapas).
    assert data["realtime_factor"] == round(data["total_seconds"] / 120.0, 2)
    assert data["realtime_factor"] >= 0


def test_effective_config_persisted(tmp_path: Path):
    report = tmp_path / "r.json"
    t = PipelineTimings(report_path=report)
    t.set_effective_config(whisper_model="large-v3", whisper_device="cpu")
    t.set_effective_config(tts_workers=3, tts_device_forced_cpu=True)
    t.record("a", 1.0)
    t.write_report(report, final=True)
    cfg = _read(report)["effective_config"]
    assert cfg == {
        "whisper_model": "large-v3",
        "whisper_device": "cpu",
        "tts_workers": 3,
        "tts_device_forced_cpu": True,
    }


def test_set_effective_config_ignores_none_values():
    t = PipelineTimings()
    t.set_effective_config(llm_model=None, tts_backend="index_tts2")
    assert t.as_dict()["effective_config"] == {"tts_backend": "index_tts2"}


def test_add_warning_accumulates_in_report(tmp_path: Path):
    report = tmp_path / "r.json"
    t = PipelineTimings(report_path=report)
    t.add_warning("audio_mixing.overflow_after_compression", segment_index=2, overflow_seconds=0.27)
    t.add_warning("container.cpu_forced", workers=3)
    t.write_report(report, final=True)
    warnings = _read(report)["warnings"]
    assert len(warnings) == 2
    assert warnings[0]["source"] == "audio_mixing.overflow_after_compression"
    assert warnings[0]["segment_index"] == 2
    assert warnings[1]["workers"] == 3
    assert all("at" in w for w in warnings)


def test_drain_warnings_returns_and_clears():
    from video_translator.utils.warning_collector import drain_warnings, note_warning

    drain_warnings()  # limpiar estado global de otros tests
    note_warning("test.source", detail=42)
    note_warning("test.other")
    out = drain_warnings()
    assert len(out) == 2
    assert out[0] == {"source": "test.source", "at": out[0]["at"], "detail": 42}
    assert drain_warnings() == []
