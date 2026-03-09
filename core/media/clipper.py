import json
import os
import subprocess
import sys
import time as _time
import uuid

from .. import config
from .crop import (
    build_cover_scale_crop_vf,
    build_cover_scale_vf,
    build_face_crop_vf,
    get_split_heights,
)
from .subtitles import (
    build_subtitle_force_style,
    escape_subtitles_filter_dir,
    escape_subtitles_filter_path,
    generate_subtitle,
)
from .hook import prepend_hook_intro
import random
from ..analysis.metadata import generate_publishing_metadata


# ─────────────────────────────────────────────────────────────────────────────
# GPU / HW Encoder Detection
# Priority: h264_nvenc (NVIDIA) → h264_amf (AMD) → h264_qsv (Intel) → libx264
# ─────────────────────────────────────────────────────────────────────────────

_encoder_checked = False
_encoder_name = "libx264"
_encoder_args = []

_ENCODER_CANDIDATES = [
    (
        "h264_nvenc",
        ["-c:v", "h264_nvenc"],
        ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "26"],
        "NVIDIA NVENC (CUDA)",
    ),
    (
        "h264_amf",
        ["-c:v", "h264_amf"],
        [
            "-c:v",
            "h264_amf",
            "-quality",
            "speed",
            "-rc",
            "cqp",
            "-qp_i",
            "26",
            "-qp_p",
            "26",
        ],
        "AMD AMF (OpenCL)",
    ),
    (
        "h264_qsv",
        ["-c:v", "h264_qsv"],
        ["-c:v", "h264_qsv", "-preset", "faster", "-global_quality", "26"],
        "Intel QSV",
    ),
]


def _detect_hw_encoder():
    """Detect the best available hardware encoder, with CPU fallback."""
    global _encoder_checked, _encoder_name, _encoder_args
    if _encoder_checked:
        return
    _encoder_checked = True

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        available = result.stdout
    except Exception:
        print("INFO ffmpeg encoder query failed, using CPU encoding")
        return

    for name, test_args, enc_args, label in _ENCODER_CANDIDATES:
        if name not in available:
            continue
        try:
            test = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "nullsrc=s=64x64:d=0.1",
                    *test_args,
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                timeout=10,
            )
            if test.returncode == 0:
                _encoder_name = name
                _encoder_args = enc_args
                print(f"INFO GPU encoding enabled: {label} ({name})")
                return
        except Exception:
            continue

    print("INFO No GPU encoder available, using CPU encoding (libx264)")


def _video_encoder_args():
    """Return video encoder args for the best available encoder."""
    _detect_hw_encoder()
    if _encoder_args:
        return list(_encoder_args) + ["-r", "30"]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-r", "30"]


def _hw_input_args():
    """Return hwaccel input args for GPU decoding, or [] for CPU."""
    _detect_hw_encoder()
    if _encoder_name == "h264_nvenc":
        return ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    if _encoder_name == "h264_amf":
        return ["-hwaccel", "d3d11va"]
    if _encoder_name == "h264_qsv":
        return ["-hwaccel", "qsv"]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Stream URL Cache  (avoid per-clip yt-dlp overhead)
# ─────────────────────────────────────────────────────────────────────────────


class _StreamURLCache:
    """Cache direct stream URLs extracted by yt-dlp for a video."""

    _cache: dict = {}
    _TTL = 600  # 10 minutes

    @classmethod
    def get(cls, video_id):
        entry = cls._cache.get(video_id)
        if entry and (_time.time() - entry["ts"]) < cls._TTL:
            return entry["video_url"], entry["audio_url"]
        return None, None

    @classmethod
    def extract(cls, video_id):
        """Extract and cache direct stream URLs via yt-dlp -g."""
        try:
            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--force-ipv4",
                "-g",
                "-f",
                "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
            ]
            if cookie_args := config.get_cookie_args():
                cmd += cookie_args
            cmd.append(f"https://youtu.be/{video_id}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return None, None

            urls = [u.strip() for u in result.stdout.strip().split("\n") if u.strip()]
            if len(urls) >= 2:
                video_url, audio_url = urls[0], urls[1]
            elif len(urls) == 1:
                video_url = audio_url = urls[0]
            else:
                return None, None

            cls._cache[video_id] = {
                "video_url": video_url,
                "audio_url": audio_url,
                "ts": _time.time(),
            }
            print(f"  Stream URLs cached for {video_id}")
            return video_url, audio_url

        except Exception as e:
            print(f"  URL extraction failed: {e}")
            return None, None

    @classmethod
    def get_or_extract(cls, video_id):
        v, a = cls.get(video_id)
        return (v, a) if v else cls.extract(video_id)


# ─────────────────────────────────────────────────────────────────────────────
# A/V Sync helpers
# ─────────────────────────────────────────────────────────────────────────────


def _probe_stream_starts(filepath):
    """
    Return (video_start, audio_start) PTS in seconds for both streams.
    Falls back to (0.0, 0.0) on any error.
    """
    try:
        # Optimization: increased analyzeduration and probesize for complex streams
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-analyzeduration",
                "20M",
                "-probesize",
                "20M",
                "-print_format",
                "json",
                "-show_entries",
                "stream=codec_type,start_time",
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        v_start = a_start = 0.0
        for s in data.get("streams", []):
            try:
                t = float(s.get("start_time", 0))
            except (TypeError, ValueError):
                t = 0.0
            if s.get("codec_type") == "video":
                v_start = t
            elif s.get("codec_type") == "audio":
                a_start = t
        return v_start, a_start
    except Exception as e:
        print(f"  A/V probe failed: {e}")
        return 0.0, 0.0


def _build_av_sync_filters(filepath):
    """
    Build (video_filter_prefix, audio_filter_prefix) trim expressions that
    align both streams to a common start point, then reset PTS to 0.

    The 'aresample=async=1000' audio safety-net corrects any residual drift
    that can accumulate across the clip (fixes the 1-in-4 desync issue).
    """
    v_start, a_start = _probe_stream_starts(filepath)
    offset = a_start - v_start

    if abs(offset) < 0.01:
        # Negligible offset – just reset PTS
        v_filter = "setpts=PTS-STARTPTS"
        a_filter = "asetpts=PTS-STARTPTS,aresample=async=1:min_comp=0.01:min_hard_comp=0.1:first_pts=0"
    elif offset > 0:
        # Video leads audio: trim the extra video head
        print(f"  A/V offset {offset:+.3f}s — trimming video start")
        v_filter = f"trim=start={v_start + offset},setpts=PTS-STARTPTS"
        a_filter = f"atrim=start={a_start},asetpts=PTS-STARTPTS,aresample=async=1:min_comp=0.01:min_hard_comp=0.1:first_pts=0"
    else:
        # Audio leads video: trim the extra audio head
        print(f"  A/V offset {offset:+.3f}s — trimming audio start")
        v_filter = f"trim=start={v_start},setpts=PTS-STARTPTS"
        a_filter = f"atrim=start={a_start + (-offset)},asetpts=PTS-STARTPTS,aresample=async=1:min_comp=0.01:min_hard_comp=0.1:first_pts=0"

    return v_filter, a_filter


# ─────────────────────────────────────────────────────────────────────────────
# Small utilities
# ─────────────────────────────────────────────────────────────────────────────


def _fire(event_hook, event: str, data: dict):
    """Safe event_hook caller — silently ignores errors."""
    if callable(event_hook):
        try:
            event_hook(event, data)
        except Exception:
            pass


def _ffmpeg_encode(
    input_file,
    output_file,
    vf=None,
    af=None,
    filter_complex=None,
    extra_map=None,
    extra_input=None,
):
    """
    Build and run an ffmpeg re-encode command.

    Args:
        input_file:     Primary input path.
        output_file:    Destination path.
        vf:             -vf filter string (ignored when filter_complex is set).
        af:             -af filter string.
        filter_complex: -filter_complex string; when provided, caller must also
                        pass extra_map to specify output stream labels.
        extra_input:    List of additional ffmpeg args inserted before the
                        primary -i (e.g. a second input file).
        extra_map:      List of -map args used with filter_complex outputs.
    """
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    if extra_input:
        cmd += extra_input

    cmd += ["-i", input_file]

    if filter_complex:
        cmd += ["-filter_complex", filter_complex]
        if extra_map:
            cmd += extra_map
    else:
        if vf:
            cmd += ["-vf", vf]
        if af:
            cmd += ["-af", af]

    cmd += [
        *_video_encoder_args(),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-avoid_negative_ts",
        "make_zero",
        output_file,
    ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)


# ─────────────────────────────────────────────────────────────────────────────
# Download helpers
# ─────────────────────────────────────────────────────────────────────────────


def _download_section_ffmpeg(video_url, audio_url, start, end, out_file):
    """Download a time slice using cached URLs via ffmpeg. Returns True on success."""
    try:
        # Common flags for network stability when fetching from URLs
        net_args = [
            "-reconnect",
            "1",
            "-reconnect_at_eof",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
        ]

        if video_url == audio_url:
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(start),
                "-to",
                str(end),
                *net_args,
                "-i",
                video_url,
                "-c",
                "copy",
                "-copyts",
                "-avoid_negative_ts",
                "disabled",
                out_file,
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(start),
                "-to",
                str(end),
                *net_args,
                "-i",
                video_url,
                *net_args,
                "-i",
                audio_url,
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c",
                "copy",
                "-copyts",
                "-avoid_negative_ts",
                "disabled",
                out_file,
            ]
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        return True
    except subprocess.CalledProcessError:
        return False


def _download_section_ytdlp(
    video_id, start, end, out_file, event_hook=None, clip_index=0
):
    """Download a section via yt-dlp with progress reporting."""
    import re

    base_cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-ipv4",
        "--newline",
        "--no-warnings",
        "--ignore-no-formats-error",
        "--extractor-args",
        "youtube:player_client=android_vr,ios,android,tv,web",
        "--download-sections",
        f"*{start}-{end}",
        "--merge-output-format",
        "mkv",
    ]
    fmt_primary = [
        "-f",
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
    ]
    fmt_fallback = ["-f", "bv*+ba/b"]
    target = ["-o", out_file, f"https://youtu.be/{video_id}"]

    def _run(cmd_args):
        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines = []
        for line in process.stdout:
            lines.append(line)
            if callable(event_hook) and "[download]" in line and "%" in line:
                m = re.search(r"\[download\]\s+([\d.]+)%.*?(?:at\s+([^\s]+))?", line)
                if m:
                    try:
                        _fire(
                            event_hook,
                            "download_progress",
                            {
                                "pct": float(m.group(1)),
                                "speed": m.group(2) or "",
                                "clip_index": clip_index,
                            },
                        )
                    except ValueError:
                        pass
        process.wait()
        if process.returncode != 0:
            err = subprocess.CalledProcessError(process.returncode, cmd_args)
            err.stderr = "".join(lines)
            raise err

    def _try(primary, fallback):
        try:
            _run(primary)
        except subprocess.CalledProcessError as e:
            if "Requested format is not available" in (e.stderr or ""):
                _run(fallback)
            else:
                raise

    cookie_args = config.get_cookie_args() or []
    primary = base_cmd + fmt_primary + cookie_args + target
    fallback = base_cmd + fmt_fallback + cookie_args + target

    try:
        _try(primary, fallback)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        # If cookies caused a failure, retry without them
        if cookie_args and ("No video formats found" in stderr or "Sign in" in stderr):
            print("  Retrying download WITHOUT cookies...")
            _try(base_cmd + fmt_primary + target, base_cmd + fmt_fallback + target)
        else:
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Crop command builders
# ─────────────────────────────────────────────────────────────────────────────


def _build_crop_cmd(
    temp_file, cropped_file, crop_mode, v_filter, a_filter, out_w, out_h
):
    """
    Return the ffmpeg command list for the crop/encode step.
    For face mode this returns None — face mode builds its own command.
    """
    is_original = config.OUTPUT_RATIO == "original"
    no_portrait = not out_w or not out_h or out_h < out_w

    if crop_mode == "default":
        if is_original:
            return _cmd_simple(temp_file, cropped_file, v_filter, a_filter)
        return _cmd_simple(
            temp_file,
            cropped_file,
            f"{v_filter},{build_cover_scale_crop_vf(out_w, out_h)}",
            a_filter,
        )

    if crop_mode == "face":
        # Caller handles face mode separately; signal with None
        return None

    if crop_mode in ("split_left", "split_right"):
        if is_original or no_portrait:
            vf = (
                None
                if is_original
                else build_cover_scale_crop_vf(out_w or 720, out_h or 1280)
            )
            composed = f"{v_filter},{vf}" if vf else v_filter
            return _cmd_simple(temp_file, cropped_file, composed, a_filter)

        top_h, bottom_h = get_split_heights(out_h)
        scaled = build_cover_scale_vf(out_w, out_h)
        right_x = "iw-{out_w}" if crop_mode == "split_right" else "0"
        fc = (
            f"{v_filter},{scaled}[scaled];"
            f"[scaled]split=2[s1][s2];"
            f"[s1]crop={out_w}:{top_h}:(iw-{out_w})/2:(ih-{out_h})/2[top];"
            f"[s2]crop={out_w}:{bottom_h}:{right_x}:ih-{bottom_h}[bottom];"
            f"[top][bottom]vstack[out]"
        )
        return [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            temp_file,
            "-filter_complex",
            fc,
            "-map",
            "[out]",
            "-map",
            "0:a?",
            "-af",
            a_filter,
            *_video_encoder_args(),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-avoid_negative_ts",
            "make_zero",
            cropped_file,
        ]

    raise ValueError(f"Unknown crop_mode: {crop_mode!r}")


def _cmd_simple(input_file, output_file, vf, af, extra_inputs=None, extra_maps=None):
    """Build a basic ffmpeg command with -vf / -af."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if extra_inputs:
        cmd += extra_inputs
    cmd += ["-i", input_file]
    cmd += ["-vf", vf, "-af", af]
    if extra_maps:
        cmd += extra_maps
    cmd += [
        *_video_encoder_args(),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-avoid_negative_ts",
        "make_zero",
        output_file,
    ]
    return cmd


# ─────────────────────────────────────────────────────────────────────────────
# Main clip processor
# ─────────────────────────────────────────────────────────────────────────────


def process_single_clip(
    video_id,
    item,
    index,
    total_duration,
    crop_mode="default",
    use_subtitle=False,
    event_hook=None,
    video_title="",
    video_description="",
    source_file=None,
):
    """
    Extract/download, crop, and export a single vertical clip.

    Args:
        video_id:          YouTube video ID.
        item:              Segment info dict (start, duration, text, …).
        index:             Clip index number.
        total_duration:    Full video length in seconds.
        crop_mode:         "default" | "face" | "split_left" | "split_right".
        use_subtitle:      Burn auto-generated subtitles into the clip.
        event_hook:        Optional callback(event, data) for progress tracking.
        video_title:       Source video title (for metadata).
        video_description: Source video description (for metadata).
        source_file:       Pre-downloaded file path. When supplied clips are
                           extracted locally (fast). None → download from YT.
    """
    start_original = item.get("start", 0)
    end_original = start_original + item.get("duration", 0)
    start = max(0, start_original - config.PADDING)
    end = min(end_original + config.PADDING, total_duration)

    if end - start < 15:
        return False

    clip_uid = uuid.uuid4().hex[:6]
    base_name = f"clip_{index}_{clip_uid}"
    temp_file = f"temp_{base_name}.mkv"
    cropped_file = f"temp_cropped_{base_name}.mp4"
    subtitle_file = f"temp_{base_name}.srt"
    dynamic_out = f"temp_dynamic_{base_name}.mp4"
    output_file = os.path.join(config.OUTPUT_DIR, f"{base_name}.mp4")
    temp_files = [temp_file, cropped_file, subtitle_file, dynamic_out]

    out_w, out_h = config.OUT_WIDTH, config.OUT_HEIGHT

    print(
        f"[Clip {index}] Processing segment "
        f"({int(start)}s – {int(end)}s, padding {config.PADDING}s)"
    )

    try:
        # ── 1. Acquire raw segment ────────────────────────────────────────
        _fire(event_hook, "stage", {"stage": "download", "clip_index": index})

        if source_file and os.path.exists(source_file):
            print(f"  Extracting from local file ({int(end - start)}s)…")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    str(start),
                    "-to",
                    str(end),
                    "-i",
                    source_file,
                    "-c",
                    "copy",
                    "-copyts",
                    "-avoid_negative_ts",
                    "disabled",
                    temp_file,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )

        else:
            # Prioritize yt-dlp for downloading sections as it's more resilient to YouTube's throttling
            print(f"  Downloading section via yt-dlp ({int(end - start)}s)…")
            try:
                _download_section_ytdlp(
                    video_id, start, end, temp_file, event_hook, index
                )
            except Exception as e:
                print(f"  yt-dlp download failed: {e}")
                print("  Retrying with cached URLs via FFmpeg...")
                video_url, audio_url = _StreamURLCache.get_or_extract(video_id)
                if video_url:
                    ok = _download_section_ffmpeg(
                        video_url, audio_url, start, end, temp_file
                    )
                    if not ok:
                        print("  Fallback download also failed.")
                else:
                    print("  No cached URLs available for fallback.")

        if not os.path.exists(temp_file):
            print("  Failed to obtain video segment.")
            return False

        # ── 2. Build A/V sync filter strings ────────────────────────────
        #
        # _build_av_sync_filters probes the downloaded MKV and returns trim
        # expressions that align both streams to the same start point, then
        # reset PTS to 0.  The 'aresample=async=1000' appended to a_filter
        # corrects any residual micro-drift that accumulates over the clip —
        # this is the primary fix for the intermittent A/V desync issue.
        #
        v_filter, a_filter = _build_av_sync_filters(temp_file)

        # ── 3. Crop / re-encode ──────────────────────────────────────────
        _fire(event_hook, "stage", {"stage": "crop", "clip_index": index})
        print("  Cropping video…")

        if crop_mode == "face" and config.OUTPUT_RATIO != "original":
            from .crop import dynamic_face_crop_video

            print("  Applying dynamic face tracking…")
            success = dynamic_face_crop_video(
                temp_file, dynamic_out, out_w, out_h, vf=v_filter
            )

            if success and os.path.exists(dynamic_out):
                # dynamic_out is now already synced (trim applied in decoder)
                # merge with re-synced audio from temp_file
                cmd_crop = [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    dynamic_out,
                    "-i",
                    temp_file,
                    "-vf",
                    "setpts=PTS-STARTPTS",
                    "-af",
                    a_filter,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0?",
                    "-shortest",
                    *_video_encoder_args(),
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-avoid_negative_ts",
                    "make_zero",
                    cropped_file,
                ]
            else:
                print("  Face tracking failed — falling back to static crop.")
                vf_static = build_face_crop_vf(
                    temp_file, out_w, out_h
                ) or build_cover_scale_crop_vf(out_w, out_h)
                cmd_crop = _cmd_simple(
                    temp_file, cropped_file, f"{v_filter},{vf_static}", a_filter
                )
        else:
            cmd_crop = _build_crop_cmd(
                temp_file, cropped_file, crop_mode, v_filter, a_filter, out_w, out_h
            )

        subprocess.run(cmd_crop, check=True, capture_output=True, text=True)

        # Clean up raw segment and dynamic temp
        for f in [temp_file, dynamic_out]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

        # ── 4. Subtitle (optional) ───────────────────────────────────────
        if use_subtitle:
            _fire(event_hook, "stage", {"stage": "subtitle", "clip_index": index})
            print("  Generating subtitle…")

            if generate_subtitle(cropped_file, subtitle_file, event_hook=event_hook):
                _fire(
                    event_hook, "stage", {"stage": "burn_subtitle", "clip_index": index}
                )
                print("  Burning subtitle…")

                sub_path = escape_subtitles_filter_path(subtitle_file)
                fonts_dir = config.SUBTITLE_FONTS_DIR
                fonts_arg = (
                    f":fontsdir='{escape_subtitles_filter_dir(fonts_dir)}'"
                    if fonts_dir and os.path.isdir(fonts_dir)
                    else ""
                )
                force_style = build_subtitle_force_style()

                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        cropped_file,
                        "-vf",
                        f"subtitles='{sub_path}'{fonts_arg}:force_style='{force_style}'",
                        *_video_encoder_args(),
                        "-c:a",
                        "copy",
                        output_file,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                os.remove(cropped_file)
                os.remove(subtitle_file)
            else:
                print("  Subtitle generation failed — continuing without subtitles.")
                _fire(event_hook, "stage", {"stage": "finalize", "clip_index": index})
                os.rename(cropped_file, output_file)
        else:
            _fire(event_hook, "stage", {"stage": "finalize", "clip_index": index})
            os.rename(cropped_file, output_file)

        # ── 4.5 Hook Intro (Updated) ───────────────────────────────────
        if config.HOOK_ENABLED:
            # Pick hook text
            # Fallback chain: publishing.hook_variants (random) -> publishing.hook -> hook_preview -> item text
            publishing = item.get("publishing", {})
            hook_variants = publishing.get("hook_variants", [])
            hook_text = ""

            if hook_variants and isinstance(hook_variants, list):
                hook_text = random.choice(hook_variants)

            if not hook_text:
                hook_text = (
                    publishing.get("hook")
                    or item.get("hook_preview")
                    or item.get("text", "")[:100]
                )

            if hook_text and os.path.exists(output_file):
                _fire(event_hook, "stage", {"stage": "hook", "clip_index": index})
                print(f'  Adding hook intro: "{hook_text[:40]}..."')

                temp_hook_output = output_file + ".hooked.mp4"
                success = prepend_hook_intro(
                    clip_path=output_file,
                    hook_text=hook_text,
                    output_path=temp_hook_output,
                    voice=config.HOOK_VOICE,
                    font_size=config.HOOK_FONT_SIZE,
                    rate=config.HOOK_VOICE_RATE,
                    pitch=config.HOOK_VOICE_PITCH,
                )
                if success and os.path.exists(temp_hook_output):
                    os.replace(temp_hook_output, output_file)
                    print("  Hook intro added successfully.")
                else:
                    print("  Failed to add hook intro.")
                    if os.path.exists(temp_hook_output):
                        os.remove(temp_hook_output)

        print("  Clip successfully generated.")

        # ── 5. Metadata ──────────────────────────────────────────────────
        meta = {
            "clip_index": index,
            "start": start_original,
            "end": end_original,
            "duration": end_original - start_original,
            "text": item.get("text", ""),
            "content_type": item.get("content_type", ""),
            "score": item.get("score", 0.0),
            "dimension_scores": item.get("dimension_scores", {}),
            "hook_preview": item.get("hook_preview", ""),
            "clip_reason": item.get("clip_reason", ""),
            "suggested_clip_title": item.get("suggested_clip_title", ""),
            "platform_fit": item.get("platform_fit", []),
            "source_video_title": video_title,
            "source_video_description": video_description,
        }

        if config.AI_API_KEY:
            _fire(event_hook, "stage", {"stage": "metadata", "clip_index": index})
            print("  Generating AI publishing metadata…")
            try:
                transcript = (
                    [
                        {
                            "text": item.get("text", ""),
                            "start": start_original,
                            "end": end_original,
                        }
                    ]
                    if item.get("text")
                    else []
                )
                publishing_meta = generate_publishing_metadata(
                    transcript_segments=transcript,
                    video_title=video_title or f"Video Clip {index}",
                    video_description=video_description or "",
                    custom_prompt=config.AI_METADATA_PROMPT or "",
                )
                if publishing_meta:
                    meta["publishing"] = publishing_meta
                    print("  Publishing metadata generated.")
            except Exception as e:
                print(f"  Publishing metadata failed: {e}")

        try:
            meta_file = os.path.join(config.OUTPUT_DIR, f"{base_name}.meta.json")
            with open(meta_file, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2, ensure_ascii=False)
            print(f"  Metadata saved → {meta_file}")
        except Exception as e:
            print(f"  Failed to save metadata: {e}")

        _fire(event_hook, "stage", {"stage": "done_clip", "clip_index": index})
        return True

    except subprocess.CalledProcessError as e:
        _cleanup(temp_files)
        print("  Failed to generate clip.")
        print(f"  Error: {e.stderr or e.stdout or e}")
        return False

    except Exception as e:
        _cleanup(temp_files)
        print("  Failed to generate clip.")
        print(f"  Error: {e}")
        return False


def _cleanup(paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
