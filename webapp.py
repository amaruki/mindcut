import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from types import SimpleNamespace

from flask import Flask, jsonify, render_template, request, send_from_directory

import core
from core import config
from core import youtube_api

app = Flask(__name__, static_folder="static", template_folder="templates")


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


def run_scan_job(job_id, payload):
    started = now_ms()
    try:
        scan_jobs.update(
            job_id,
            status="running",
            started_at=started,
            stage="init",
            pct=0,
            status_text="starting",
        )
        cleanup_temp_files(max_age_hours=6)

        url = (payload.get("url") or "").strip()
        if not url:
            raise ValueError("URL kosong")

        mode = payload.get("mode") or "heatmap"
        ai_api_url = (payload.get("ai_api_url") or "").strip()
        ai_model = (payload.get("ai_model") or "").strip()
        ai_api_key = (payload.get("ai_api_key") or "").strip()
        ai_prompt = (payload.get("ai_prompt") or "").strip()
        ai_metadata_prompt = (payload.get("ai_metadata_prompt") or "").strip()
        cookies_browser = (payload.get("cookies_browser") or "").strip()
        core.set_ai_config(
            api_url=ai_api_url or None,
            model=ai_model or None,
            api_key=ai_api_key or None,
            segment_prompt=ai_prompt or None,
            metadata_prompt=ai_metadata_prompt or None,
            cookies_browser=cookies_browser or None,
        )

        core.cek_dependensi._args = SimpleNamespace(no_update_ytdlp=True)
        ok = core.cek_dependensi(install_whisper=False, fatal=False)
        if not ok:
            raise RuntimeError("FFmpeg tidak ketemu")

        video_id = core.extract_video_id(url)
        if not video_id:
            raise ValueError("URL YouTube invalid")

        if scan_jobs.get(job_id).get("cancelled"):
            return

        video_title, video_description = fetch_video_metadata(url)

        transcript_segments = []
        heatmap_segments = []
        segments = []

        scan_jobs.update(
            job_id, stage="transcribe", pct=10, status_text="fetching subtitles"
        )

        if scan_jobs.get(job_id).get("cancelled"):
            return

        # Always try to fetch subtitles for metadata context, but only consider missing
        # subtitles an error/warning if mode depends on it.
        transcript_segments = core.get_transcript_segments(
            video_id, allow_whisper_fallback=False
        )

        if not transcript_segments and mode in ("ai", "combined"):
            scan_jobs.update(
                job_id,
                status_text="no subtitles found, using heatmap only",
                warning="No YouTube subtitles/captions found for this video. AI analysis skipped. Using heatmap data only.",
            )

        if scan_jobs.get(job_id).get("cancelled"):
            return

        scan_jobs.update(job_id, stage="heatmap", pct=70, status_text="fetch heatmap")
        heatmap_segments = core.ambil_most_replayed(video_id)

        # Inject transcript text into heatmap segments early so the UI and combined analysis have it
        if transcript_segments and heatmap_segments:
            for seg in heatmap_segments:
                clip_start = seg.get("start", 0)
                clip_end = clip_start + seg.get("duration", 0)
                matched_texts = []
                for ts in transcript_segments:
                    ts_end = ts["start"] + ts.get("duration", 0)
                    if ts["start"] < clip_end and ts_end > clip_start:
                        matched_texts.append(ts["text"])
                if matched_texts:
                    seg["text"] = " ".join(matched_texts)

        if scan_jobs.get(job_id).get("cancelled"):
            return

        if mode == "ai" or mode == "combined":
            if transcript_segments:
                scan_jobs.update(job_id, stage="ai", pct=85, status_text="ai scoring")
                # analyze_transcript_with_ai does the full pipeline:
                # heuristic → heatmap → AI → fuse → NMS → rank
                segments = core.analyze_transcript_with_ai(
                    transcript_segments,
                    video_title,
                    video_description,
                    custom_prompt=ai_prompt,
                    heatmap_segments=heatmap_segments,
                )
            else:
                segments = heatmap_segments
        else:
            segments = heatmap_segments

        metadata = {}
        if ai_metadata_prompt and mode in ("ai", "combined"):
            scan_jobs.update(job_id, stage="metadata", pct=93, status_text="metadata")
            metadata = core.generate_publishing_metadata(
                transcript_segments or [],
                video_title,
                video_description,
                heatmap_segments=heatmap_segments,
                candidate_segments=segments,
                custom_prompt=ai_metadata_prompt,
            )

        duration = core.get_duration(video_id)
        warning = (scan_jobs.get(job_id) or {}).get("warning", "")
        scan_jobs.update(
            job_id,
            status="done",
            stage="done",
            pct=100,
            status_text="done",
            finished_at=now_ms(),
            result={
                "video_id": video_id,
                "duration": duration,
                "segments": segments,
                "heatmap_segments": heatmap_segments,
                "transcript_segments": transcript_segments,
                "analysis_mode": mode,
                "metadata": metadata,
                "warning": warning,
            },
        )
    except Exception as e:
        scan_jobs.update(
            job_id,
            status="error",
            error=str(e),
            finished_at=now_ms(),
            stage="error",
            pct=100,
        )


def run_job(job_id, payload):
    started = now_ms()
    try:
        jobs.update(job_id, status="running", started_at=started)

        url = (payload.get("url") or "").strip()
        if not url:
            raise ValueError("URL kosong")

        crop = payload.get("crop") or "default"
        ratio = payload.get("ratio") or "9:16"
        subtitle = bool(payload.get("subtitle"))
        whisper_model = payload.get("whisper_model") or "small"
        subtitle_font = payload.get("subtitle_font") or "Arial"
        subtitle_location = payload.get("subtitle_location") or "bottom"
        subtitle_fontsdir = payload.get("subtitle_fontsdir") or None
        if not subtitle_fontsdir and os.path.isdir("fonts"):
            subtitle_fontsdir = "fonts"
        padding = safe_int(payload.get("padding"), 10)
        max_clips = safe_int(payload.get("max_clips"), 10)
        mode = payload.get("mode") or "heatmap"
        ai_api_url = (payload.get("ai_api_url") or "").strip()
        ai_model = (payload.get("ai_model") or "").strip()
        ai_api_key = (payload.get("ai_api_key") or "").strip()
        ai_prompt = (payload.get("ai_prompt") or "").strip()
        ai_metadata_prompt = (payload.get("ai_metadata_prompt") or "").strip()
        cookies_browser = (payload.get("cookies_browser") or "").strip()
        hook_enabled = bool(payload.get("hook_enabled"))
        hook_voice = payload.get("hook_voice") or "en-US-GuyNeural"
        hook_voice_rate = payload.get("hook_voice_rate") or "+15%"
        hook_voice_pitch = payload.get("hook_voice_pitch") or "+5Hz"
        hook_font_size = safe_int(payload.get("hook_font_size"), 72)
        jobs.update(job_id, subtitle_enabled=subtitle)

        config.WHISPER_MODEL = whisper_model
        config.SUBTITLE_FONT = subtitle_font
        config.SUBTITLE_FONTS_DIR = subtitle_fontsdir
        config.SUBTITLE_LOCATION = subtitle_location
        config.PADDING = max(0, padding if padding is not None else 10)
        config.HOOK_ENABLED = hook_enabled
        config.HOOK_VOICE = hook_voice
        config.HOOK_VOICE_RATE = hook_voice_rate
        config.HOOK_VOICE_PITCH = hook_voice_pitch
        config.HOOK_FONT_SIZE = hook_font_size
        config.set_ratio_preset(ratio)
        core.set_ai_config(
            api_url=ai_api_url or None,
            model=ai_model or None,
            api_key=ai_api_key or None,
            segment_prompt=ai_prompt or None,
            metadata_prompt=ai_metadata_prompt or None,
            cookies_browser=cookies_browser or None,
        )

        job_dir = os.path.join("clips", job_id)
        os.makedirs(job_dir, exist_ok=True)
        config.OUTPUT_DIR = job_dir

        core.cek_dependensi._args = SimpleNamespace(no_update_ytdlp=True)
        ok = core.cek_dependensi(install_whisper=subtitle, fatal=False)
        if not ok:
            raise RuntimeError("FFmpeg tidak ketemu")

        video_id = core.extract_video_id(url)
        if not video_id:
            raise ValueError("URL YouTube invalid")

        total_duration = core.get_duration(video_id)
        video_title, video_description = fetch_video_metadata(url)

        # Always try to fetch subtitles for metadata context (fast, no whisper fallback)
        jobs.add_log(job_id, "Fetching subtitles for metadata context...")
        transcript_segments = core.get_transcript_segments(
            video_id, allow_whisper_fallback=False
        )

        targets = []
        picked = payload.get("segments")
        if isinstance(picked, list) and len(picked) > 0:
            jobs.add_log(job_id, f"Pakai {len(picked)} segment yang dipilih...")
            for seg in picked:
                try:
                    start = float(seg.get("start"))
                    dur = float(seg.get("duration"))
                    score = float(seg.get("score", 1.0))
                except Exception:
                    continue
                if dur <= 0:
                    continue
                target = {"start": start, "duration": dur, "score": score}
                # Preserve analysis fields for metadata persistence
                for key in (
                    "end",
                    "text",
                    "content_type",
                    "hook_preview",
                    "clip_reason",
                    "suggested_clip_title",
                    "platform_fit",
                    "dimension_scores",
                    "original_index",
                ):
                    if key in seg:
                        target[key] = seg[key]
                targets.append(target)
            if not targets:
                raise ValueError("Segment pilihan invalid")
        elif mode == "custom":
            start_s = parse_time_to_seconds(payload.get("start"))
            end_s = parse_time_to_seconds(payload.get("end"))
            if start_s is None or end_s is None:
                raise ValueError("Start/End belum diisi")
            if end_s <= start_s:
                raise ValueError("End harus lebih besar dari Start")
            targets = [
                {
                    "start": float(start_s),
                    "duration": float(end_s - start_s),
                    "score": 1.0,
                }
            ]
        else:
            if mode in ("ai", "combined"):
                jobs.add_log(
                    job_id, "Scan heatmap (transcribe deferred to clip stage)..."
                )
                segments = core.ambil_most_replayed(video_id)
                if not segments:
                    raise RuntimeError("Tidak ada heatmap/Most Replayed data")
                targets = segments[: max(1, max_clips or 10)]
            else:
                jobs.add_log(job_id, "Scan heatmap...")
                segments = core.ambil_most_replayed(video_id)
                if not segments:
                    raise RuntimeError("Tidak ada heatmap/Most Replayed data")
                targets = segments[: max(1, max_clips or 10)]

        jobs.update(job_id, total=len(targets), done=0, status_text="processing")

        def event_hook(kind, data):
            if kind == "download_progress" and isinstance(data, dict):
                jobs.update(job_id, dl_pct=data.get("pct"), dl_speed=data.get("speed"))
            elif kind == "stage" and isinstance(data, dict):
                stage = data.get("stage") or ""
                clip_index = safe_int(data.get("clip_index"), 0) or 0
                jobs.update(
                    job_id,
                    stage=stage,
                    stage_at=now_ms(),
                    stage_clip=clip_index,
                    dl_pct=0,
                    dl_speed="",
                )

        success = 0
        for idx, item in enumerate(targets, start=1):
            clip_num = item.get("original_index", idx)
            jobs.update(
                job_id,
                current=idx,
                status_text=f"clip {clip_num} ({idx}/{len(targets)})",
            )

            # Match transcript segments to this clip for rich AI text context
            if transcript_segments:
                clip_start = item.get("start", 0)
                clip_end = clip_start + item.get("duration", 0)
                matched_texts = []
                for ts in transcript_segments:
                    ts_end = ts["start"] + ts.get("duration", 0)
                    if ts["start"] < clip_end and ts_end > clip_start:
                        matched_texts.append(ts["text"])
                if matched_texts:
                    item["text"] = " ".join(matched_texts)

            ok = core.process_single_clip(
                video_id,
                item,
                clip_num,
                total_duration,
                crop,
                subtitle,
                event_hook=event_hook,
                video_title=video_title,
                video_description=video_description,
            )
            if ok:
                success += 1
            jobs.update(
                job_id, done=idx, success=success, outputs=list_outputs(job_dir)
            )

        jobs.update(
            job_id, status="done", finished_at=now_ms(), outputs=list_outputs(job_dir)
        )
    except Exception as e:
        jobs.update(job_id, status="error", error=str(e), finished_at=now_ms())


def get_preview(url):
    key = url.strip()
    if not key:
        raise ValueError("URL kosong")

    cached = preview_cache.get(key)
    if cached:
        return cached

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "-J",
        key,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout or "Gagal ambil metadata").strip())

    raw = json.loads(res.stdout)
    item = (
        raw["entries"][0]
        if isinstance(raw, dict) and "entries" in raw and raw.get("entries")
        else raw
    )

    preview = {
        "title": item.get("title"),
        "thumbnail": item.get("thumbnail"),
        "uploader": item.get("uploader"),
        "duration": item.get("duration"),
        "webpage_url": item.get("webpage_url") or key,
        "id": item.get("id"),
    }

    preview_cache.set(key, preview)

    return preview


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/settings")
def settings_page():
    return render_template("settings.html")


@app.get("/assets/fonts/<path:filename>")
def serve_font(filename):
    return send_from_directory("fonts", filename, as_attachment=False)


@app.post("/api/preview")
def api_preview():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    try:
        preview = get_preview(url)
        return jsonify({"ok": True, "preview": preview})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/analyze-transcript")
def api_analyze_transcript():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    ai_api_url = (data.get("ai_api_url") or "").strip()
    ai_model = (data.get("ai_model") or "").strip()
    ai_api_key = (data.get("ai_api_key") or "").strip()
    ai_prompt = (data.get("ai_prompt") or "").strip()
    ai_metadata_prompt = (data.get("ai_metadata_prompt") or "").strip()
    cookies_browser = (data.get("cookies_browser") or "").strip()
    video_id = core.extract_video_id(url)
    if not video_id:
        return jsonify({"ok": False, "error": "URL YouTube invalid"}), 400

    core.cek_dependensi._args = SimpleNamespace(no_update_ytdlp=True)
    ok = core.cek_dependensi(install_whisper=False, fatal=False)
    if not ok:
        return jsonify({"ok": False, "error": "FFmpeg tidak ketemu"}), 400
    core.set_ai_config(
        api_url=ai_api_url or None,
        model=ai_model or None,
        api_key=ai_api_key or None,
        segment_prompt=ai_prompt or None,
        metadata_prompt=ai_metadata_prompt or None,
        cookies_browser=cookies_browser or None,
    )

    # Get video metadata for context
    video_title, video_description = fetch_video_metadata(url)

    # Extract transcript segments
    transcript_segments = core.get_transcript_segments(video_id)

    if not transcript_segments:
        return jsonify({"ok": False, "error": "No transcript segments found"}), 400

    # Analyze with AI — full pipeline (heuristic → heatmap → AI → fuse → NMS)
    heatmap_segments = core.ambil_most_replayed(video_id)
    segments = core.analyze_transcript_with_ai(
        transcript_segments,
        video_title,
        video_description,
        custom_prompt=ai_prompt,
        heatmap_segments=heatmap_segments,
    )

    total_duration = core.get_duration(video_id)

    metadata = {}
    if ai_metadata_prompt:
        metadata = core.generate_publishing_metadata(
            transcript_segments,
            video_title,
            video_description,
            heatmap_segments=heatmap_segments,
            candidate_segments=segments,
            custom_prompt=ai_metadata_prompt,
        )

    return jsonify(
        {
            "ok": True,
            "video_id": video_id,
            "duration": total_duration,
            "segments": segments,
            "transcript_segments": transcript_segments,
            "heatmap_segments": heatmap_segments,
            "metadata": metadata,
        }
    )


@app.post("/api/scan")
def api_scan():
    data = request.get_json(silent=True) or {}
    job_id = uuid.uuid4().hex[:12]
    scan_jobs.create(
        job_id,
        {
            "id": job_id,
            "status": "queued",
            "created_at": now_ms(),
            "started_at": None,
            "finished_at": None,
            "error": None,
            "stage": "",
            "pct": 0,
            "status_text": "",
            "result": None,
            "cancelled": False,
        },
    )
    t = threading.Thread(target=run_scan_job, args=(job_id, data), daemon=True)
    t.start()
    return jsonify({"ok": True, "job_id": job_id})


@app.post("/api/scan/start")
def api_scan_start():
    return api_scan()


@app.get("/api/scan/job/<job_id>")
def api_scan_job(job_id):
    job = scan_jobs.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Scan job not found"}), 404
    return jsonify({"ok": True, "job": job})


@app.post("/api/scan/cancel/<job_id>")
def api_scan_cancel(job_id):
    ok = scan_jobs.cancel(job_id)
    cleanup_temp_files(max_age_hours=6)
    if not ok:
        return jsonify({"ok": False, "error": "Scan job not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/clip")
def api_clip():
    payload = request.get_json(silent=True) or {}

    url = (payload.get("url") or "").strip()
    title = payload.get("video_title", "")

    # Fallback and try to fetch metadata if frontend didn't supply a title
    if not title and url:
        try:
            fetched_title, _ = fetch_video_metadata(url)
            title = fetched_title
        except Exception:
            pass

    if title:
        safe_title = re.sub(r"[^\w\s-]", "", title).strip()
        safe_title = re.sub(r"[-\s]+", "-", safe_title).lower()
        if len(safe_title) > 50:
            safe_title = safe_title[:50]
        safe_title = safe_title.strip("-")
        job_id = safe_title if safe_title else uuid.uuid4().hex[:12]
    else:
        # Fallback to random hex if no title is available
        job_id = uuid.uuid4().hex[:12]

    job_dir = os.path.join("clips", job_id)
    existing_outputs = list_outputs(job_dir) if os.path.isdir(job_dir) else []

    jobs.create(
        job_id,
        {
            "id": job_id,
            "status": "queued",
            "created_at": now_ms(),
            "started_at": None,
            "finished_at": None,
            "error": None,
            "total": 0,
            "done": 0,
            "success": 0,
            "current": 0,
            "status_text": "",
            "stage": "",
            "stage_at": None,
            "stage_clip": 0,
            "subtitle_enabled": False,
            "outputs": existing_outputs,
            "logs": [],
        },
    )

    t = threading.Thread(target=run_job, args=(job_id, payload), daemon=True)
    t.start()
    return jsonify({"ok": True, "job_id": job_id})


@app.get("/api/job/<job_id>")
def api_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    return jsonify({"ok": True, "job": job})


@app.get("/api/gallery")
def api_gallery():
    groups = {}
    if os.path.exists("clips"):
        for job_id in os.listdir("clips"):
            job_dir = os.path.join("clips", job_id)
            if os.path.isdir(job_dir):
                job_items = []
                for name in os.listdir(job_dir):
                    if name.lower().endswith(".mp4"):
                        path = os.path.join(job_dir, name)

                        # Look for metadata file
                        meta_path = os.path.join(
                            job_dir, name.replace(".mp4", ".meta.json")
                        )
                        has_metadata = os.path.exists(meta_path)
                        is_uploaded = False

                        if has_metadata:
                            try:
                                with open(meta_path, "r", encoding="utf-8") as f:
                                    meta_data = json.load(f)
                                    is_uploaded = meta_data.get("uploaded", False)
                            except Exception:
                                pass

                        job_items.append(
                            {
                                "job_id": job_id,
                                "filename": name,
                                "path": f"/clips/{job_id}/{name}",  # Web path
                                "size": os.path.getsize(path),
                                "created": os.path.getctime(path),
                                "has_metadata": has_metadata,
                                "is_uploaded": is_uploaded,
                            }
                        )

                if job_items:
                    job_items.sort(key=lambda x: x["created"], reverse=True)
                    groups[job_id] = {
                        "job_id": job_id,
                        "items": job_items,
                        "created": max(item["created"] for item in job_items),
                    }

    # Sort groups by most recent clip
    sorted_groups = sorted(groups.values(), key=lambda x: x["created"], reverse=True)
    return jsonify({"ok": True, "groups": sorted_groups})


@app.post("/api/gallery/delete")
def api_gallery_delete():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    filename = data.get("filename")

    if not job_id or not filename:
        return jsonify({"ok": False, "error": "Missing job_id or filename"}), 400

    job_dir = os.path.join("clips", job_id)
    file_path = os.path.join(job_dir, filename)
    meta_path = os.path.join(job_dir, filename.replace(".mp4", ".meta.json"))

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)

        # If directory is empty, remove it
        if os.path.exists(job_dir) and not os.listdir(job_dir):
            os.rmdir(job_dir)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/gallery/delete-group")
def api_gallery_delete_group():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")

    if not job_id:
        return jsonify({"ok": False, "error": "Missing job_id"}), 400

    job_dir = os.path.join("clips", job_id)

    try:
        if os.path.exists(job_dir):
            import shutil

            shutil.rmtree(job_dir)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/youtube/accounts")
def api_youtube_accounts():
    try:
        accounts = youtube_api.get_accounts()
        return jsonify({"ok": True, "accounts": accounts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/youtube/accounts/link")
def api_youtube_link_account():
    try:
        account = youtube_api.link_new_account()
        return jsonify({"ok": True, "account": account})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/youtube/upload")
def api_youtube_upload():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    title = data.get("title", "My Short Video")
    description = data.get("description", "")
    tags = data.get("tags", [])
    privacy = data.get("privacy", "private")
    publish_at = data.get("publish_at", None)
    account_id = data.get("account_id", None)

    if not job_id or not filename:
        return jsonify({"ok": False, "error": "Missing job_id or filename"}), 400

    file_path = os.path.join("clips", job_id, filename)
    if not os.path.exists(file_path):
        return jsonify({"ok": False, "error": "File not found"}), 404

    # YouTube no longer supports standalone tags via the API.
    # Strategy: fit as many tags as hashtags into the title (max 100 chars),
    # then append all remaining tags as #hashtags at the end of the description.
    MAX_TITLE_LEN = 100
    hashtag_tags = [f"#{t.strip().replace(' ', '')}" for t in tags if t.strip()]

    # Try to append hashtags to the title without exceeding 100 chars
    title_base = title[:MAX_TITLE_LEN].rstrip()
    title_tags_used = []
    remaining_tags = list(hashtag_tags)
    for ht in hashtag_tags:
        candidate = title_base + " " + " ".join(title_tags_used + [ht])
        if len(candidate) <= MAX_TITLE_LEN:
            title_tags_used.append(ht)
            remaining_tags.remove(ht)
        else:
            break  # no more room

    if title_tags_used:
        title_final = (title_base + " " + " ".join(title_tags_used)).strip()
    else:
        title_final = title_base

    # Append remaining (or all) hashtags to description
    desc_final = description
    if hashtag_tags:
        hashtag_line = " ".join(remaining_tags if title_tags_used else hashtag_tags)
        desc_final = (description.rstrip() + "\n\n" + hashtag_line).strip()

    try:
        video_id = youtube_api.upload_video(
            file_path=file_path,
            title=title_final,
            description=desc_final,
            tags=[],
            privacy_status=privacy,
            publish_at=publish_at,
            account_id=account_id,
        )

        # Mark as uploaded in metadata if it exists
        meta_path = os.path.join(
            "clips", str(job_id), str(filename).replace(".mp4", ".meta.json")
        )
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
                meta_data["uploaded"] = True
                meta_data["youtube_id"] = video_id
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)
            except Exception as e:
                print(f"Error updating metadata uploaded status: {e}")

        return jsonify({"ok": True, "youtube_id": video_id})
    except Exception as e:
        error_msg = str(e)
        if "uploadLimitExceeded" in error_msg:
            return jsonify(
                {
                    "ok": False,
                    "error": "YouTube daily upload limit reached. You can only upload a limited number of videos per day (typically around 6-10 for new channels). Please try again in 24 hours.",
                }
            ), 429
        return jsonify({"ok": False, "error": error_msg}), 500


@app.get("/upload-manager")
def upload_manager():
    return render_template("upload_manager.html")


@app.get("/api/clips/metadata")
def api_get_clip_metadata():
    job_id = request.args.get("job_id")
    filename = request.args.get("filename")

    if not job_id or not filename:
        return jsonify({"ok": False, "error": "Missing job_id or filename"}), 400

    meta_path = os.path.join(
        "clips", str(job_id), str(filename).replace(".mp4", ".meta.json")
    )
    if not os.path.exists(meta_path):
        return jsonify({"ok": True, "metadata": None})

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
        return jsonify({"ok": True, "metadata": meta_data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/clips/metadata/save")
def api_save_clip_metadata():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    metadata = data.get("metadata")

    if not job_id or not filename or not metadata:
        return jsonify({"ok": False, "error": "Missing required fields"}), 400

    meta_path = os.path.join(
        "clips", str(job_id), str(filename).replace(".mp4", ".meta.json")
    )

    # Merge with existing if available
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                existing.update(metadata)
                metadata = existing
        except Exception:
            pass

    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/clips/metadata/generate")
def api_generate_clip_metadata():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    custom_prompt = data.get("custom_prompt", "")

    if not job_id or not filename:
        return jsonify({"ok": False, "error": "Missing job_id or filename"}), 400

    # Read text from existing metadata if available
    meta_path = os.path.join(
        "clips", str(job_id), str(filename).replace(".mp4", ".meta.json")
    )
    transcript_segments = []
    video_title = f"Video Clip from {job_id}"
    video_description = ""

    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

                # Retrieve saved full-context if available
                if "transcript_segments" in existing:
                    transcript_segments = existing["transcript_segments"]
                elif "text" in existing:
                    transcript_segments = [
                        {"text": existing["text"], "start": 0, "end": 0}
                    ]

                if "source_video_title" in existing:
                    video_title = existing["source_video_title"]
                if "source_video_description" in existing:
                    video_description = existing["source_video_description"]
        except Exception:
            pass

    try:
        meta = core.generate_publishing_metadata(
            transcript_segments=transcript_segments,
            video_title=video_title,
            video_description=video_description,
            custom_prompt=custom_prompt or core.config.AI_METADATA_PROMPT,
        )
        if meta:
            # Save under "publishing" key, consistent with clipper.py
            save_data = {}
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    save_data = json.load(f)
            save_data["publishing"] = meta
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)

            return jsonify({"ok": True, "metadata": meta})
        else:
            return jsonify({"ok": False, "error": "AI returned empty metadata"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/clips/<job_id>/<path:filename>")
def serve_clip(job_id, filename):
    job_dir = os.path.join("clips", job_id)
    return send_from_directory(job_dir, filename, as_attachment=True)


@app.post("/api/tts/preview")
def api_tts_preview():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "This is a preview of the hook voice.")
    voice = data.get("voice", "en-US-GuyNeural")
    rate = data.get("rate", "+15%")
    pitch = data.get("pitch", "+5Hz")

    import asyncio
    from core.media.hook import generate_tts

    os.makedirs("temp_preview", exist_ok=True)
    filename = f"preview_{uuid.uuid4().hex}.mp3"
    path = os.path.join("temp_preview", filename)

    try:
        asyncio.run(generate_tts(text, voice, path, rate=rate, pitch=pitch))
        return send_from_directory("temp_preview", filename)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/clips/hook")
def api_add_hook_manual():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    voice = data.get("voice") or config.HOOK_VOICE
    rate = data.get("rate") or config.HOOK_VOICE_RATE
    pitch = data.get("pitch") or config.HOOK_VOICE_PITCH
    font_size = safe_int(data.get("font_size"), config.HOOK_FONT_SIZE)

    if not job_id or not filename:
        return jsonify({"ok": False, "error": "Missing job_id or filename"}), 400

    clip_path = os.path.join("clips", str(job_id), str(filename))
    meta_path = clip_path.replace(".mp4", ".meta.json")

    if not os.path.exists(clip_path) or not os.path.exists(meta_path):
        return jsonify({"ok": False, "error": "Clip or metadata not found"}), 404

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Pick hook text
        import random

        publishing = meta.get("publishing", {})
        hook_variants = publishing.get("hook_variants", [])
        hook_text = ""
        if hook_variants and isinstance(hook_variants, list):
            hook_text = random.choice(hook_variants)
        if not hook_text:
            hook_text = (
                publishing.get("hook")
                or meta.get("hook_preview")
                or meta.get("text", "")[:100]
            )

        if not hook_text:
            return jsonify(
                {"ok": False, "error": "No hook text found in metadata"}
            ), 400

        from core.media.hook import prepend_hook_intro

        temp_output = clip_path + ".manual_hook.mp4"
        success = prepend_hook_intro(
            clip_path=clip_path,
            hook_text=hook_text,
            output_path=temp_output,
            voice=voice,
            font_size=font_size,
            rate=rate,
            pitch=pitch,
        )

        if success and os.path.exists(temp_output):
            os.replace(temp_output, clip_path)
            # Update meta
            meta["has_hook"] = True
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            return jsonify({"ok": True})
        else:
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return jsonify({"ok": False, "error": "Hook generation failed"}), 500

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
