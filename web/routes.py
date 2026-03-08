import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from types import SimpleNamespace

from flask import Blueprint, jsonify, render_template, request, send_from_directory

import core
from core import config
from core import youtube_api
from core.media.hook import generate_tts, prepend_hook_intro

from web.jobs import run_job, run_scan_job
from web.store import jobs, preview_cache, scan_jobs
from web.utils import (
    cleanup_temp_files,
    fetch_video_metadata,
    list_outputs,
    now_ms,
    parse_time_to_seconds,
    safe_int,
)

bp = Blueprint("api", __name__)


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


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/settings")
def settings_page():
    return render_template("settings.html")


@bp.get("/assets/fonts/<path:filename>")
def serve_font(filename):
    return send_from_directory("fonts", filename, as_attachment=False)


@bp.post("/api/preview")
def api_preview():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    try:
        preview = get_preview(url)
        return jsonify({"ok": True, "preview": preview})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/api/settings/extract-cookies")
def api_extract_cookies():
    data = request.get_json(silent=True) or {}
    browser = (data.get("browser") or "").strip()
    if not browser or browser == "none":
        return jsonify({"ok": False, "error": "Please select a valid browser."}), 400

    try:
        cmd = [
            "yt-dlp",
            "--cookies",
            "cookies.txt",
            "--cookies-from-browser",
            browser,
            "--skip-download",
            "--flat-playlist",
            "--playlist-items",
            "0",
            "https://www.youtube.com",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            err = (res.stderr or res.stdout or "").strip()
            return jsonify({"ok": False, "error": f"Failed to extract: {err}"}), 400

        if not os.path.exists("cookies.txt"):
            return jsonify(
                {"ok": False, "error": "Extracted but cookies.txt was not created."}
            ), 500

        size = os.path.getsize("cookies.txt")
        if size < 10:
            return jsonify(
                {"ok": False, "error": "cookies.txt is empty. Are you logged in?"}
            ), 400

        return jsonify(
            {
                "ok": True,
                "message": "Cookies extracted and saved to cookies.txt successfully.",
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/api/analyze-transcript")
def api_analyze_transcript():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    max_clips = safe_int(data.get("max_clips"), 10)
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

    video_title, video_description = fetch_video_metadata(url)
    transcript_segments = core.get_transcript_segments(video_id)

    if not transcript_segments:
        return jsonify({"ok": False, "error": "No transcript segments found"}), 400

    heatmap_segments = core.ambil_most_replayed(video_id)
    segments = core.analyze_transcript_with_ai(
        transcript_segments,
        video_title,
        video_description,
        custom_prompt=ai_prompt,
        heatmap_segments=heatmap_segments,
        max_clips=max_clips,
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


@bp.post("/api/scan")
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


@bp.post("/api/scan/start")
def api_scan_start():
    return api_scan()


@bp.get("/api/scan/job/<job_id>")
def api_scan_job(job_id):
    job = scan_jobs.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Scan job not found"}), 404
    return jsonify({"ok": True, "job": job})


@bp.post("/api/scan/cancel/<job_id>")
def api_scan_cancel(job_id):
    ok = scan_jobs.cancel(job_id)
    cleanup_temp_files(max_age_hours=6)
    if not ok:
        return jsonify({"ok": False, "error": "Scan job not found"}), 404
    return jsonify({"ok": True})


@bp.post("/api/clip")
def api_clip():
    payload = request.get_json(silent=True) or {}

    url = (payload.get("url") or "").strip()
    title = payload.get("video_title", "")

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


@bp.get("/api/job/<job_id>")
def api_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    return jsonify({"ok": True, "job": job})


@bp.get("/api/gallery")
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
                                "path": f"/clips/{job_id}/{name}",
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

    sorted_groups = sorted(groups.values(), key=lambda x: x["created"], reverse=True)
    return jsonify({"ok": True, "groups": sorted_groups})


@bp.post("/api/gallery/delete")
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

        if os.path.exists(job_dir) and not os.listdir(job_dir):
            os.rmdir(job_dir)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/api/gallery/delete-group")
def api_gallery_delete_group():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")

    if not job_id:
        return jsonify({"ok": False, "error": "Missing job_id"}), 400

    job_dir = os.path.join("clips", job_id)

    try:
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/api/youtube/accounts")
def api_youtube_accounts():
    try:
        accounts = youtube_api.get_accounts()
        return jsonify({"ok": True, "accounts": accounts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/api/youtube/accounts/link")
def api_youtube_link_account():
    try:
        account = youtube_api.link_new_account()
        return jsonify({"ok": True, "account": account})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/api/youtube/upload")
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

    MAX_TITLE_LEN = 100
    hashtag_tags = [f"#{t.strip().replace(' ', '')}" for t in tags if t.strip()]

    title_base = title[:MAX_TITLE_LEN].rstrip()
    title_tags_used = []
    remaining_tags = list(hashtag_tags)
    for ht in hashtag_tags:
        candidate = title_base + " " + " ".join(title_tags_used + [ht])
        if len(candidate) <= MAX_TITLE_LEN:
            title_tags_used.append(ht)
            remaining_tags.remove(ht)
        else:
            break

    if title_tags_used:
        title_final = (title_base + " " + " ".join(title_tags_used)).strip()
    else:
        title_final = title_base

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


@bp.get("/upload-manager")
def upload_manager():
    return render_template("upload_manager.html")


@bp.get("/scheduled")
def scheduled_page():
    return render_template("scheduled.html")


@bp.get("/api/youtube/videos")
def api_youtube_videos():
    account_id = request.args.get("account_id") or None
    max_results = min(int(request.args.get("max_results", 50)), 50)
    try:
        videos = youtube_api.list_channel_videos(
            account_id=account_id, max_results=max_results
        )
        return jsonify({"ok": True, "videos": videos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/api/clips/metadata")
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


@bp.post("/api/clips/metadata/save")
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


@bp.post("/api/clips/metadata/generate")
def api_generate_clip_metadata():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    custom_prompt = data.get("custom_prompt", "")

    if not job_id or not filename:
        return jsonify({"ok": False, "error": "Missing job_id or filename"}), 400

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


@bp.get("/clips/<job_id>/<path:filename>")
def serve_clip(job_id, filename):
    job_dir = os.path.join("clips", job_id)
    return send_from_directory(job_dir, filename, as_attachment=True)


@bp.post("/api/tts/preview")
def api_tts_preview():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "This is a preview of the hook voice.")
    voice = data.get("voice", "en-US-GuyNeural")
    rate = data.get("rate", "+15%")
    pitch = data.get("pitch", "+5Hz")

    os.makedirs("temp_preview", exist_ok=True)
    filename = f"preview_{uuid.uuid4().hex}.mp3"
    path = os.path.join("temp_preview", filename)

    try:
        asyncio.run(generate_tts(text, voice, path, rate=rate, pitch=pitch))
        return send_from_directory("temp_preview", filename)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/api/clips/hook")
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
