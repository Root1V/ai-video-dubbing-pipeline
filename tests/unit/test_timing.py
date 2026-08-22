from __future__ import annotations

import time
from pathlib import Path

from video_translator.utils.timing import PipelineTimings


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
    import json

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["stages"][0]["name"] == "stage_a"
