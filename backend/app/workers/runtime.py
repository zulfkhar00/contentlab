"""
Production worker runtime.

Polls the jobs table with SELECT ... FOR UPDATE SKIP LOCKED.
Dispatches to registered handlers.
Heartbeats every worker_heartbeat_interval seconds.
Graceful shutdown on SIGTERM/SIGINT.

Usage:
    python -m app.workers.runtime
    # or
    PYTHONPATH=backend python3 -m app.workers.runtime
"""
import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from typing import Callable, Awaitable

from sqlalchemy import text

from app.config import settings
from app.db.session import AsyncSessionLocal

log = logging.getLogger("worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Handler registry: job_type → async callable
_HANDLERS: dict[str, Callable[[dict], Awaitable[dict]]] = {}


def register_handler(job_type: str):
    """Decorator to register a job handler."""
    def decorator(fn: Callable[[dict], Awaitable[dict]]):
        _HANDLERS[job_type] = fn
        return fn
    return decorator


async def _claim(worker_id: str, job_types: list[str], lease_seconds: int) -> dict | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT * FROM claim_job(:wid::text, :types::text[], :lease::integer)"),
            {"wid": worker_id, "types": job_types, "lease": lease_seconds},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def _heartbeat_loop(worker_id: str, job_id: str, stop: asyncio.Event) -> None:
    interval = settings.worker_heartbeat_interval
    while not stop.is_set():
        await asyncio.sleep(interval)
        if stop.is_set():
            break
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("SELECT extend_job_lease(:jid, :wid, :secs)"),
                    {"jid": job_id, "wid": worker_id, "secs": settings.worker_lease_seconds},
                )
        except Exception as exc:
            log.warning("Heartbeat failed for job %s: %s", job_id, exc)


async def _complete(worker_id: str, job_id: str, result: dict) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT complete_job(:jid, :wid, :result)"),
            {"jid": job_id, "wid": worker_id, "result": json.dumps(result)},
        )


async def _fail(worker_id: str, job_id: str, error: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT fail_job(:jid, :wid, :err)"),
            {"jid": job_id, "wid": worker_id, "err": error},
        )


async def _process_job(worker_id: str, job: dict) -> None:
    job_id = str(job["id"])
    job_type = job["job_type"]
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    handler = _HANDLERS.get(job_type)
    if not handler:
        log.error("No handler registered for job_type=%s job_id=%s", job_type, job_id)
        await _fail(worker_id, job_id, f"No handler for job_type: {job_type}")
        return

    log.info("Starting job %s type=%s attempt=%s", job_id, job_type, job.get("attempt_count", 1))
    t_start = time.monotonic()

    hb_stop = asyncio.Event()
    hb_task = asyncio.create_task(_heartbeat_loop(worker_id, job_id, hb_stop))

    try:
        result = await handler({**job, "payload": payload})
        await _complete(worker_id, job_id, result or {})
        elapsed = int((time.monotonic() - t_start) * 1000)
        log.info("Completed job %s in %dms", job_id, elapsed)
    except Exception as exc:
        elapsed = int((time.monotonic() - t_start) * 1000)
        log.error("Failed job %s after %dms: %s", job_id, elapsed, exc)
        await _fail(worker_id, job_id, str(exc)[:500])
    finally:
        hb_stop.set()
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass


async def run(
    worker_id: str | None = None,
    job_types: list[str] | None = None,
) -> None:
    """
    Main worker loop. Runs until SIGTERM/SIGINT.
    Registers all handlers from app.workers.handlers before starting.
    """
    # Auto-import handlers to trigger @register_handler decorators
    import app.workers.handlers  # noqa: F401

    wid = worker_id or settings.worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    types = job_types  # None = claim any type

    log.info("Worker %s starting (job_types=%s)", wid, types or "any")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop():
        log.info("Worker %s received stop signal", wid)
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (RuntimeError, NotImplementedError):
            pass  # Windows / non-main thread

    poll = settings.worker_poll_interval
    lease = settings.worker_lease_seconds

    while not stop.is_set():
        job = await _claim(wid, types, lease)
        if not job:
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll)
            except asyncio.TimeoutError:
                pass
            continue
        await _process_job(wid, job)

    log.info("Worker %s stopped", wid)


def main() -> None:
    """Entrypoint for `python -m app.workers.runtime`."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
