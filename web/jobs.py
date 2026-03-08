import os
from types import SimpleNamespace

import core
from core import config

from web.store import jobs, scan_jobs
from web.utils import (
    cleanup_temp_files,
    fetch_video_metadata,
    list_outputs,
    now_ms,
    parse_time_to_seconds,
    safe_int,
)


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
        max_clips = safe_int(payload.get("max_clips"), 10)
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
                    max_clips=max_clips,
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
