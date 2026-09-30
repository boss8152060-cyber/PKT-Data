"""Shared background job manager for PK Studio.

Jobs never touch Tk widgets directly. UI callbacks can be marshalled back to
the Tk event loop by passing ``ui_call`` from a widget (usually ``widget.after``).
"""
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional, Any


@dataclass
class Job:
    target: Callable[[threading.Event], Any]
    on_done: Optional[Callable[["Job"], None]] = None
    on_error: Optional[Callable[["Job"], None]] = None
    ui_call: Optional[Callable[..., Any]] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    cancel_event: threading.Event = field(default_factory=threading.Event)
    status: str = "pending"
    error: Optional[BaseException] = None
    result: Any = None

    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def cancel(self) -> None:
        self.cancel_event.set()
        if self.status in {"pending", "running"}:
            self.status = "cancelling"

    def start(self) -> "Job":
        threading.Thread(target=self._run, daemon=True, name=f"PKJob-{self.id}").start()
        return self

    def _dispatch(self, callback: Callable[["Job"], None]) -> None:
        if self.ui_call:
            self.ui_call(callback, self)
        else:
            callback(self)

    def _run(self) -> None:
        self.status = "running"
        try:
            self.result = self.target(self.cancel_event)
        except Exception as exc:
            self.error = exc
            self.status = "error"
            traceback.print_exc()
            self._safe_dispatch(self.on_error)
            return
        self.status = "cancelled" if self.cancelled() else "done"
        self._safe_dispatch(self.on_done)

    def _safe_dispatch(self, callback) -> None:
        """A failing UI callback must not be reported as a job failure."""
        if not callback:
            return
        try:
            self._dispatch(callback)
        except Exception:
            traceback.print_exc()

class JobManager:
    def __init__(self):
        self.jobs = {}
        self._lock = threading.Lock()

    def start(self, target, on_done=None, on_error=None, ui_call=None) -> Job:
        job = Job(target, on_done, on_error, ui_call)
        with self._lock:
            self.jobs[job.id] = job
        return job.start()

    def active(self):
        with self._lock:
            return [j for j in self.jobs.values() if j.status in {"pending", "running", "cancelling"}]

    def cancel_all(self) -> None:
        for job in self.active():
            job.cancel()

    def forget_finished(self) -> None:
        with self._lock:
            self.jobs = {k: v for k, v in self.jobs.items() if v.status in {"pending", "running", "cancelling"}}
