"""A small in-process job queue with a fixed pool of workers.

Why this exists: scoring a call runs the local model several times, so it is
heavy. If the API tried to score every incoming request at once, a burst of
150 would bury a single Mac, stall the whole service, and push the machine
into swapping to the SSD. This queue stops that.

How it works:
  - A request is accepted instantly and placed in a line (the queue). The
    caller gets back a job id straight away, it does not wait for scoring.
  - A fixed number of worker threads (MAX_CONCURRENT) pull jobs off the line
    and score them. The model therefore never runs more than MAX_CONCURRENT
    jobs at the same time. Everything else waits its turn.
  - The result is stored under the job id, and the caller fetches it later.

This is deliberately simple: in memory, single process. It is exactly the
shape the team asked for (accept, queue, work a few at a time, never overload).
To scale past one machine later, swap this for a real queue (for example Redis
with a task runner) and keep the same submit / get / snapshot interface.

Tune how many run at once with the QA_MAX_CONCURRENT environment variable.
On a single Mac keep it small (2 to 3): each score runs the model a few times,
so too many at once just brings back the overload this is meant to prevent.
"""

import os
import queue
import threading
import uuid
from datetime import datetime, timezone

# How many jobs may be scored at the same time. Small on purpose (see above).
MAX_CONCURRENT = int(os.environ.get("QA_MAX_CONCURRENT", "2"))

# The most jobs the system will hold at once: the ones being scored plus the
# few waiting. Once this is reached, new requests are turned away with a
# "busy, retry shortly" instead of being queued, so the app never holds a huge
# backlog in memory. Set QA_CAPACITY=2 to only ever accept what is being scored
# (the strictest "reject the rest" behaviour); raise it for a bigger buffer.
CAPACITY = int(os.environ.get("QA_CAPACITY", "10"))

# How long to tell a turned-away caller to wait before trying again (seconds).
RETRY_AFTER = int(os.environ.get("QA_RETRY_AFTER", "10"))

_jobs = {}                 # job_id -> job record (includes the raw payload)
_lock = threading.Lock()   # guards _jobs, _seq and _active
_pending = queue.Queue()   # job_ids waiting to be scored, in arrival order
_seq = 0                   # running count, for a human-friendly job number
_active = 0                # jobs in the system now (queued + processing)
_started = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def _public(job):
    """A copy safe to hand back over the API (drops the raw payload)."""
    if job is None:
        return None
    return {k: v for k, v in job.items() if k != "payload"}


def submit(payload):
    """Try to accept a scoring request.

    Returns (True, job_record) if there was room and the job was queued, or
    (False, info) if the system is at capacity. In the busy case, info carries
    the current counts and how long to wait, so the caller can be told to
    retry. Nothing is stored for a rejected request.
    """
    global _seq, _active
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        if _active >= CAPACITY:
            running = sum(1 for j in _jobs.values()
                          if j["status"] == "processing")
            return False, {
                "waiting": _active - running,
                "processing": running,
                "capacity": CAPACITY,
                "retry_after": RETRY_AFTER,
            }
        _seq += 1
        _active += 1
        job = {
            "id": job_id,
            "number": _seq,
            "status": "queued",       # queued -> processing -> done | error
            "submitted_at": _now(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
            "payload": payload,
        }
        _jobs[job_id] = job
        record = _public(job)
    _pending.put(job_id)
    return True, record


def get(job_id):
    """Return a job record by id, or None if there is no such job."""
    with _lock:
        return _public(_jobs.get(job_id))


def snapshot():
    """A view of the whole queue: counts plus every job, oldest first.

    This is the 'log' the team wanted: what is waiting, what is running now,
    and what has finished.
    """
    with _lock:
        jobs = [_public(j) for j in _jobs.values()]
    counts = {"queued": 0, "processing": 0, "done": 0, "error": 0}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    active = counts["queued"] + counts["processing"]
    return {
        "max_concurrent": MAX_CONCURRENT,
        "capacity": CAPACITY,
        "free_slots": max(0, CAPACITY - active),
        "waiting": counts["queued"],
        "running": counts["processing"],
        "done": counts["done"],
        "failed": counts["error"],
        "jobs": sorted(jobs, key=lambda j: j["number"]),
    }


def start_workers(score_fn):
    """Start the fixed pool of worker threads once.

    score_fn(payload) does the actual scoring and returns a result dict. It is
    passed in (rather than imported) so this module stays independent of the
    web app and easy to test on its own.
    """
    global _started
    with _lock:
        if _started:
            return
        _started = True
    for i in range(MAX_CONCURRENT):
        threading.Thread(
            target=_worker_loop, args=(score_fn,),
            name=f"qa-worker-{i + 1}", daemon=True,
        ).start()


def _worker_loop(score_fn):
    """One worker: take the next job, score it, store the outcome, repeat."""
    global _active
    while True:
        job_id = _pending.get()          # blocks until a job is available
        try:
            with _lock:
                job = _jobs.get(job_id)
                if job is None:
                    _active = max(0, _active - 1)
                    continue
                job["status"] = "processing"
                job["started_at"] = _now()
                payload = job["payload"]
            try:
                result = score_fn(payload)
                status, value, err = "done", result, None
            except Exception as exc:     # never let one bad job kill the worker
                status, value, err = "error", None, str(exc)
            with _lock:
                job = _jobs.get(job_id)
                if job is not None:
                    job["status"] = status
                    job["result"] = value
                    job["error"] = err
                    job["finished_at"] = _now()
                # this job is finished, so it frees a slot for a new request
                _active = max(0, _active - 1)
        finally:
            _pending.task_done()
