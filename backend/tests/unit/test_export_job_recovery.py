from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select


def _import_fresh_app_modules() -> None:
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)


def test_recover_interrupted_export_jobs_marks_pending_and_processing_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "false")
    _import_fresh_app_modules()

    from app.db import async_session_factory, ensure_db_initialized, recover_interrupted_export_jobs
    from app.models import ExportJob

    async def seed_jobs() -> None:
        await ensure_db_initialized()
        async with async_session_factory() as db:
            db.add_all(
                [
                    ExportJob(id="job-pending", format="pdf", status="pending", progress=0.0, request_json="{}"),
                    ExportJob(id="job-processing", format="gif", status="processing", progress=55.0, request_json="{}"),
                    ExportJob(id="job-completed", format="csv", status="completed", progress=100.0, request_json="{}"),
                ]
            )
            await db.commit()

    async def load_jobs() -> dict[str, ExportJob]:
        async with async_session_factory() as db:
            rows = (await db.execute(select(ExportJob))).scalars().all()
            return {row.id: row for row in rows}

    asyncio.run(seed_jobs())
    recovered_count = asyncio.run(recover_interrupted_export_jobs())
    jobs = asyncio.run(load_jobs())

    assert recovered_count == 2

    assert jobs["job-pending"].status == "failed"
    assert jobs["job-pending"].message == "Failed"
    assert jobs["job-pending"].completed_at is not None
    assert jobs["job-pending"].error == "Interrupted while queued/running (server restart or worker interruption)."

    assert jobs["job-processing"].status == "failed"
    assert jobs["job-processing"].message == "Failed"
    assert jobs["job-processing"].completed_at is not None
    assert jobs["job-processing"].error == "Interrupted while queued/running (server restart or worker interruption)."

    assert jobs["job-completed"].status == "completed"
