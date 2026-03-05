import os
import asyncio
import subprocess
import edge_tts
import shutil
from .. import config
from .crop import _probe_video, _detect_faces_on_thumbnail, _load_haar_cascade


def find_face_frame(video_path, num_samples=10):
    """
    Extracts several frames from the video and returns the path to the frame
    with the largest detected face.
    """
    probe = _probe_video(video_path)
    if not probe:
        return None

    in_w, in_h, fps, total_frames = probe
    duration = total_frames / fps if fps else 0
    if duration <= 0:
        return None

    cascade = _load_haar_cascade()
    temp_dir = os.path.join(config.OUTPUT_DIR, "temp_hooks")
    os.makedirs(temp_dir, exist_ok=True)

    best_frame_path = None
    max_face_area = -1

    # Sample frames across the first 30% of the video or first 10 seconds
    sample_limit = min(duration * 0.3, 10.0)
    for i in range(num_samples):
        timestamp = (sample_limit / num_samples) * i
        frame_name = f"frame_{i}.png"
        frame_path = os.path.join(temp_dir, frame_name)

        # Extract 1 frame at timestamp
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            frame_path,
        ]
        subprocess.run(cmd, capture_output=True, check=False)

        if not os.path.exists(frame_path):
            continue

        # Detect faces
        import cv2

        img = cv2.imread(frame_path)
        if img is None:
            continue

        # Downscale for faster detection
        thumb_w = 320
        thumb_h = int(in_h * thumb_w / in_w)
        thumb = cv2.resize(img, (thumb_w, thumb_h))

        faces = _detect_faces_on_thumbnail(thumb, cascade, in_w, in_h)

        if faces:
            # Since crop.py sorts faces by area descending, first == largest
            if max_face_area == -1:
                best_frame_path = frame_path
                max_face_area = 1
            else:
                os.remove(frame_path)
        else:
            # Keep first frame as fallback if no face found at all
            if i == 0 and best_frame_path is None:
                best_frame_path = frame_path
            else:
                try:
                    os.remove(frame_path)
                except Exception:
                    pass

    return best_frame_path


async def generate_tts(text, voice, output_path, rate="+0%", pitch="+0Hz"):
    """Generates TTS and returns duration in seconds."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)

    # Get duration via ffprobe
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        output_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        return float(res.stdout.strip())
    except Exception:
        return 2.0


def prepend_hook_intro(
    clip_path,
    hook_text,
    output_path,
    voice="en-US-GuyNeural",
    font_size=72,
    rate="+0%",
    pitch="+0Hz",
):
    """
    Creates a hook intro segment (freeze frame + text overlay + TTS audio)
    and prepends it seamlessly to the clip using the FFmpeg concat filter.
    """
    temp_dir = os.path.join(config.OUTPUT_DIR, "temp_hooks_proc")
    os.makedirs(temp_dir, exist_ok=True)

    # ── 1. Find best frame with a face ───────────────────────────────────────
    face_frame = find_face_frame(clip_path)
    if not face_frame:
        return False

    # ── 2. Generate TTS ───────────────────────────────────────────────────────
    tts_audio = os.path.join(temp_dir, "hook_audio.mp3")
    duration = asyncio.run(
        generate_tts(hook_text, voice, tts_audio, rate=rate, pitch=pitch)
    )
    duration += 0.5  # brief pause at end before clip starts

    # ── 3. Read clip specs ────────────────────────────────────────────────────
    probe = _probe_video(clip_path)
    if not probe:
        return False
    w, h, fps, _ = probe
    fps = fps or 30

    # Detect original clip audio sample rate so we preserve it
    sr_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        clip_path,
    ]
    sr_res = subprocess.run(sr_cmd, capture_output=True, text=True, check=False)
    try:
        sample_rate = int(sr_res.stdout.strip())
    except Exception:
        sample_rate = 44100

    # ── 4. Build hook segment (freeze video + TTS audio) ─────────────────────
    hook_segment = os.path.join(temp_dir, "hook_segment.mp4")

    def wrap_text(text, limit=25):
        words = text.split()
        lines, curr = [], []
        for word in words:
            if len(" ".join(curr + [word])) > limit:
                lines.append(" ".join(curr))
                curr = [word]
            else:
                curr.append(word)
        if curr:
            lines.append(" ".join(curr))
        return "\n".join(lines)

    wrapped_text = wrap_text(hook_text)
    lines = wrapped_text.split("\n")

    # Resolve the font path — Montserrat ExtraBold for bold, premium look
    font_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "fonts",
        "Montserrat",
        "static",
        "Montserrat-ExtraBold.ttf",
    )
    # Escape backslashes and colons for FFmpeg on Windows
    font_path_escaped = font_path.replace("\\", "/").replace(":", "\\:")

    def escape_drawtext(s):
        """Escape a string for FFmpeg drawtext text= value."""
        # Strip to pure ASCII to avoid any font rendering issues
        s = s.encode("ascii", errors="ignore").decode("ascii")
        # FFmpeg drawtext escaping (order matters)
        s = s.replace("\\", "\\\\")
        s = s.replace("'", "")  # FFmpeg text='...' cannot contain literal quotes
        s = s.replace(":", "\\:")
        s = s.replace("%", "%%")
        s = s.replace(";", "\\;")
        return s

    # FFmpeg filter chain:
    #   1) Scale the still image to clip dimensions
    #   2) Loop it into a continuous stream
    #   3) Apply heavy gaussian blur (sigma=30) for cinematic backdrop
    #   4) Overlay a dark semi-transparent layer (black @ 55% opacity)
    #   5) One drawtext per line — each independently centered with x=(w-tw)/2
    #      y is calculated so the entire text block is vertically centered
    line_height = int(font_size * 1.3)  # font_size + line spacing
    total_text_height = line_height * len(lines)
    # y offset for the first line so the block is vertically centered
    y_start = f"(h-{total_text_height})/2"

    filter_parts = [
        f"scale={w}:{h}:flags=lanczos",
        f"loop=loop=-1:size=1:start=0",
        f"gblur=sigma=30",
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.55:t=fill",
    ]
    for i, line in enumerate(lines):
        escaped_line = escape_drawtext(line.strip())
        y_expr = f"{y_start}+{i * line_height}"
        dt = (
            f"drawtext=text='{escaped_line}'"
            f":fontfile='{font_path_escaped}'"
            f":fontcolor=white:fontsize={font_size}"
            f":x=(w-tw)/2:y={y_expr}"
        )
        filter_parts.append(dt)

    filter_str = ",".join(filter_parts)

    ret = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            face_frame,
            "-i",
            tts_audio,
            "-vf",
            filter_str,
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(int(fps)),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(sample_rate),
            "-shortest",
            hook_segment,
        ],
        capture_output=True,
        check=False,
    )

    if ret.returncode != 0:
        print("Hook segment error:", ret.stderr.decode(errors="replace")[-600:])
        return False

    # ── 5. Seamless concat via the FFmpeg concat filter ───────────────────────
    #
    # Both streams must be normalised to identical:
    #   • pixel format  (yuv420p)
    #   • resolution    (w×h)
    #   • frame rate    (fps)
    #   • SAR           (1:1)
    #   • audio layout  (stereo)
    #   • sample rate
    # After concat we reset PTS so there are no timestamp discontinuities.
    target_fps = int(fps)

    concat_filter = (
        f"[0:v]scale={w}:{h}:flags=lanczos,fps={target_fps},format=yuv420p,setsar=1[v0];"
        f"[1:v]scale={w}:{h}:flags=lanczos,fps={target_fps},format=yuv420p,setsar=1[v1];"
        f"[0:a]aformat=sample_rates={sample_rate}:channel_layouts=stereo[a0];"
        f"[1:a]aformat=sample_rates={sample_rate}:channel_layouts=stereo[a1];"
        f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa];"
        f"[outv]setpts=PTS-STARTPTS[vfinal];"
        f"[outa]asetpts=PTS-STARTPTS[afinal]"
    )

    ret2 = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            hook_segment,
            "-i",
            clip_path,
            "-filter_complex",
            concat_filter,
            "-map",
            "[vfinal]",
            "-map",
            "[afinal]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(target_fps),
            "-video_track_timescale",
            str(target_fps * 1000),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ac",
            "2",
            "-ar",
            str(sample_rate),
            "-movflags",
            "+faststart",
            output_path,
        ],
        capture_output=True,
        check=False,
    )

    if ret2.returncode != 0:
        print("Hook concat error:", ret2.stderr.decode(errors="replace")[-800:])

    # ── 6. Cleanup temp files ─────────────────────────────────────────────────
    try:
        shutil.rmtree(temp_dir)
        shutil.rmtree(os.path.join(config.OUTPUT_DIR, "temp_hooks"))
    except Exception:
        pass

    return os.path.exists(output_path)
