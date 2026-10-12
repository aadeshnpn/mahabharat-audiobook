"""Single background worker for render, assemble, QA, pronunciation, and voice design.

Jobs live in SQLite. A restart requeues anything left in ``running``; render and
pronunciation synth skip files that are already cached, so the interrupted line
is the only work that is repeated. Only one job runs at a time: VoxCPM2 needs
most of a 16 GB machine.
"""

from __future__ import annotations

import threading
import time
import traceback

from mbh.studio.runners import HEAVY, handler_for

_wake = threading.Event()
_pause = threading.Event()
_pause.set()
_start_lock = threading.Lock()
_started = False
_store = None


class JobContext:
    def __init__(self, store, job_id: int):
        self.store = store
        self.job_id = job_id
        self.proc = None

    def cancelled(self) -> bool:
        job = self.store.get_job(self.job_id)
        return bool(job and job.get("cancel"))

    def log(self, text: str, progress: float | None = None, message: str | None = None) -> None:
        if text and not text.endswith("\n"):
            text += "\n"
        self.store.append_log(self.job_id, text, progress=progress, message=message)


def start(store) -> None:
    """Start the worker once. Safe to call from import and from the ASGI startup hook."""
    global _started, _store
    _store = store
    with _start_lock:
        if _started:
            return
        store.recover_jobs()
        _started = True
        threading.Thread(target=_loop, name="mbh-jobs", daemon=True).start()


def enqueue(store, *, kind: str, params: dict, character_id: str | None = None, episode_id: str | None = None) -> dict:
    if kind not in HEAVY:
        raise ValueError(f"unknown job kind {kind!r}")
    job = store.add_job(character_id, kind, params, episode_id=episode_id)
    _wake.set()
    return job


def pause_worker() -> None:
    """Block the worker before it claims another job. Used by tests."""
    _pause.clear()


def resume_worker() -> None:
    _pause.set()
    _wake.set()


def cancel(store, job_id: int) -> dict | None:
    job = store.get_job(job_id)
    if not job:
        return None
    if job["status"] in {"done", "failed", "cancelled"}:
        return job
    store.request_cancel(job_id)
    _wake.set()
    return store.get_job(job_id)


def _loop() -> None:
    while True:
        _pause.wait()
        store = _store
        if store is None:
            time.sleep(0.2)
            continue
        job = store.claim_next_job()
        if job is None:
            _wake.wait(0.25)
            _wake.clear()
            continue
        ctx = JobContext(store, job["id"])
        try:
            handler_for(job["kind"])(store, job, ctx)
        except Exception:
            current = store.get_job(job["id"])
            if current and current["status"] == "running":
                store.append_log(job["id"], traceback.format_exc())
                store.update_job(
                    job["id"], status="failed", finished=time.time(),
                    message="failed", log=((current.get("log") or "") + traceback.format_exc())[-20000:],
                )
        else:
            current = store.get_job(job["id"])
            if current and current["status"] == "running":
                store.update_job(job["id"], status="failed", finished=time.time(), message="handler did not finish")
