import threading

from web.utils import now_ms


class JobStore:
    def __init__(self, max_logs=300):
        self._lock = threading.Lock()
        self._jobs = {}
        self._max_logs = max_logs

    def create(self, job_id, initial):
        with self._lock:
            self._jobs[job_id] = dict(initial)

    def get(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id, **patch):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update(patch)

    def add_log(self, job_id, line):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["logs"].append(line)
            if len(job["logs"]) > self._max_logs:
                job["logs"] = job["logs"][-self._max_logs :]


class ScanJobStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs = {}

    def create(self, job_id, initial):
        with self._lock:
            self._jobs[job_id] = dict(initial)

    def get(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id, **patch):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update(patch)

    def cancel(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job["cancelled"] = True
            job["status"] = "cancelled"
            job["finished_at"] = now_ms()
            return True


class PreviewCache:
    def __init__(self, max_items=200):
        self._lock = threading.Lock()
        self._cache = {}
        self._max_items = max_items

    def get(self, key):
        with self._lock:
            return self._cache.get(key)

    def set(self, key, value):
        with self._lock:
            self._cache[key] = value
            if len(self._cache) > self._max_items:
                self._cache.clear()


jobs = JobStore()
scan_jobs = ScanJobStore()
preview_cache = PreviewCache()
