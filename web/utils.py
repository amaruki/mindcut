import json
import os
import subprocess
import sys
import time


def now_ms():
    return int(time.time() * 1000)


def safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def parse_time_to_seconds(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    parts = s.split(":")
    if len(parts) == 2:
        m, sec = parts
        return int(m) * 60 + int(float(sec))
    if len(parts) == 3:
        h, m, sec = parts
        return int(h) * 3600 + int(m) * 60 + int(float(sec))
    return None


def list_outputs(job_dir):
    if not os.path.isdir(job_dir):
        return []
    items = []
    for name in os.listdir(job_dir):
        path = os.path.join(job_dir, name)
        if os.path.isfile(path) and name.lower().endswith(".mp4"):
            items.append({"name": name, "size": os.path.getsize(path)})
    items.sort(key=lambda x: x["name"])
    return items


def cleanup_temp_files(max_age_hours=6):
    cutoff = time.time() - (max_age_hours * 3600)
    for name in os.listdir("."):
        if not name.startswith("temp_"):
            continue
        path = os.path.join(".", name)
        if not os.path.isfile(path):
            continue
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except Exception:
            pass


def fetch_video_metadata(url):
    try:
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--skip-download",
            "-J",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return "", ""
        raw = json.loads(res.stdout)
        item = (
            raw["entries"][0]
            if isinstance(raw, dict) and "entries" in raw and raw.get("entries")
            else raw
        )
        return item.get("title", ""), item.get("description", "")
    except Exception:
        return "", ""
