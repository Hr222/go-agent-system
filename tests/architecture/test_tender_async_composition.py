from __future__ import annotations

from pathlib import Path

from app.business.agents.tender.ports.task_port import InMemoryTenderTaskResultStore
from app.composition import task as task_composition


def test_tender_worker_composition_exposes_only_fixed_task_type(monkeypatch) -> None:  # noqa: ANN001
    captured = {}

    def fake_build_task_worker(session, **kwargs):  # noqa: ANN001
        captured.update(kwargs)
        return "worker"

    monkeypatch.setattr(task_composition, "build_task_worker", fake_build_task_worker)

    worker = task_composition.build_tender_task_worker(
        object(),
        worker_id="tender-worker-1",
        tender_application=object(),
        attachment_storage=object(),
        result_store=InMemoryTenderTaskResultStore(),
    )

    assert worker == "worker"
    assert set(captured["executors"]) == {"tender.generate_bid_skeleton"}
    assert captured["worker_id"] == "tender-worker-1"


def test_tender_worker_composition_keeps_result_resources_in_fixed_binding() -> None:
    assert task_composition.__file__ is not None
    source = Path(task_composition.__file__).read_text(encoding="utf-8")

    assert "FilesystemTenderTaskResultStore" in source
    assert "attachment_storage=attachment_storage" in source
    assert "tender.generate_bid_skeleton" in source
