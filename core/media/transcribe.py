import os
import subprocess
import sys

from .. import config
from .ffmpeg import coba_masukkan_ffmpeg_ke_path, ffmpeg_tersedia


def get_model_size(model):
    """
    Get the approximate size of a Whisper model.
    """
    sizes = {
        "tiny": "75 MB",
        "base": "142 MB",
        "small": "466 MB",
        "medium": "1.5 GB",
        "large-v1": "2.9 GB",
        "large-v2": "2.9 GB",
        "large-v3": "2.9 GB"
    }
    return sizes.get(model, "unknown size")


def cek_dependensi(install_whisper=False, fatal=True):
    """
    Ensure required dependencies are available.
    Automatically updates yt-dlp and checks FFmpeg availability.
    """
    args = getattr(cek_dependensi, "_args", None)
    skip_update = bool(getattr(args, "no_update_ytdlp", False)) if args else False

    if not skip_update:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    if install_whisper:
        # Check if faster-whisper package is installed
        try:
            import faster_whisper
            print("OK Faster-Whisper package installed.")

            # Check if selected model is cached
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            model_name = f"faster-whisper-{config.WHISPER_MODEL}"

            model_cached = False
            if os.path.exists(cache_dir):
                try:
                    cached_items = os.listdir(cache_dir)
                    model_cached = any(model_name in item.lower() for item in cached_items)
                except Exception:
                    pass

            if model_cached:
                print(f"OK Model '{config.WHISPER_MODEL}' already cached and ready.\n")
            else:
                print(f"WARN Model '{config.WHISPER_MODEL}' not found in cache.")
                print(f"INFO Will auto-download ~{get_model_size(config.WHISPER_MODEL)} on first transcribe.")
                print("INFO Download happens only once, then cached for future use.\n")

        except ImportError:
            print("INFO Installing Faster-Whisper package...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("OK Faster-Whisper package installed successfully.")
            print(
                f"WARN Model '{config.WHISPER_MODEL}' (~{get_model_size(config.WHISPER_MODEL)}) "
                "will be downloaded on first use.\n"
            )

    coba_masukkan_ffmpeg_ke_path()
    if not ffmpeg_tersedia():
        print("FFmpeg not found. Please install FFmpeg and ensure it is in PATH.")
        if fatal:
            sys.exit(1)
        return False
    return True


def _transcribe_with_whisper(input_path):
    from faster_whisper import WhisperModel
    model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
    return model.transcribe(input_path, language="id")


def _to_wav(input_path, output_path):
    base = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-fflags", "+discardcorrupt",
        "-err_detect", "ignore_err",
        "-i", input_path,
        "-vn", "-ac", "1", "-ar", "16000",
        "-acodec", "pcm_s16le",
        output_path
    ]
    try:
        subprocess.run(base, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return output_path
    except Exception:
        # Retry without err_detect flags
        fallback = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path,
            "-vn", "-ac", "1", "-ar", "16000",
            "-acodec", "pcm_s16le",
            output_path
        ]
        subprocess.run(fallback, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return output_path


def get_transcript_segments(video_id, video_file=None, allow_whisper_fallback=True):
    """
    Extract transcript segments from video.
    First tries YouTube's own subtitles/captions (fast, no resource usage).
    If allow_whisper_fallback is True, falls back to Whisper transcription.
    If allow_whisper_fallback is False, returns empty list when no subtitles found.
    """
    temp_files = []
    if not video_file:
        # Try downloading JSON3 subtitles first (faster)
        import glob
        import json
        
        temp_sub = f"temp_{video_id}"
        cmd_sub_base = [
            sys.executable, "-m", "yt_dlp",
            # "--force-ipv4",
            "--quiet", "--no-warnings",
            "--write-auto-subs", "--write-subs",
            "--sub-langs", "id.*,en.*",
            "--sub-format", "json3",
            "--skip-download",
            "-o", temp_sub,
            f"https://youtu.be/{video_id}"
        ]
        
        sub_files = []
        cookie_args = config.get_cookie_args()
        if cookie_args:
            cmd_sub = cmd_sub_base + cookie_args
            subprocess.run(cmd_sub, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sub_files = glob.glob(f"temp_{video_id}*.json3")
            
        if not sub_files:
            # Try without cookies
            subprocess.run(cmd_sub_base, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sub_files = glob.glob(f"temp_{video_id}*.json3")

        if sub_files:
            # Parse json3
            transcript_segments = []
            try:
                with open(sub_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for ev in data.get("events", []):
                        if "segs" not in ev:
                            continue
                        text = "".join(seg.get("utf8", "") for seg in ev["segs"]).strip()
                        if not text or text == "\n":
                            continue
                        start_ms = ev.get("tStartMs", 0)
                        duration_ms = ev.get("dDurationMs", 0)
                        transcript_segments.append({
                            "start": start_ms / 1000.0,
                            "duration": duration_ms / 1000.0,
                            "text": text,
                            "score": 0.0
                        })
                        
                # Clean up subtitles
                for sub_file in sub_files:
                    try:
                        os.remove(sub_file)
                    except:
                        pass
                
                if transcript_segments:
                    print(f"INFO Successfully extracted {len(transcript_segments)} subtitle segments via yt-dlp.")
                    return transcript_segments
            except Exception as e:
                print(f"Failed to parse yt-dlp subtitles: {e}")
                
        # No YouTube subtitles found
        if not allow_whisper_fallback:
            print("INFO No YouTube subtitles/captions found for this video. Skipping transcription.")
            return []

        # If subtitles fail, fallback to downloading video for Whisper
        print("INFO No subtitles found via yt-dlp. Falling back to downloading audio for Whisper transcription...")
        temp_video = f"temp_{video_id}.mp4"
        try:
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "--force-ipv4",
                "--quiet", "--no-warnings",
                "--concurrent-fragments", "5",
                "--http-chunk-size", "10M",
                "--merge-output-format", "mp4",
                "-f",
                "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
                "-o", temp_video,
                f"https://youtu.be/{video_id}"
            ]
            cookie_args = config.get_cookie_args()
            if cookie_args:
                cmd_cookies = cmd + cookie_args
                try:
                    subprocess.run(cmd_cookies, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except subprocess.CalledProcessError as e:
                    print(f"Warning: Whisper audio fallback with cookies failed. Retrying without cookies... Error: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)}")
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
            video_file = temp_video
            temp_files.append(temp_video)
        except Exception as e:
            print(f"Failed to download video: {e}")
            return []

    try:
        try:
            segments, info = _transcribe_with_whisper(video_file)
        except Exception:
            # Fallback: transcribe from WAV extracted by ffmpeg
            temp_wav = f"temp_{video_id}_audio.wav"
            _to_wav(video_file, temp_wav)
            temp_files.append(temp_wav)
            segments, info = _transcribe_with_whisper(temp_wav)

        transcript_segments = []
        for segment in segments:
            transcript_segments.append({
                "start": segment.start,
                "duration": segment.end - segment.start,
                "text": segment.text.strip(),
                "score": 0.0  # Will be updated by AI analysis
            })

        # Clean up temp files
        for f in temp_files:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        return transcript_segments

    except Exception:
        # Try audio-only download as last resort
        try:
            temp_wav = f"temp_{video_id}_audio.wav"
            cmd_audio = [
                sys.executable, "-m", "yt_dlp",
                "--force-ipv4",
                "--quiet", "--no-warnings",
                "-x", "--audio-format", "wav",
                "-o", f"temp_{video_id}_audio.%(ext)s",
                f"https://youtu.be/{video_id}"
            ]
            if config.COOKIES_BROWSER:
                cmd_audio.extend(["--cookies-from-browser", config.COOKIES_BROWSER])
            subprocess.run(cmd_audio, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            temp_files.append(temp_wav)
            if not os.path.exists(temp_wav):
                # fallback: if yt-dlp didn't output wav, attempt convert
                temp_audio = f"temp_{video_id}_audio.m4a"
                if os.path.exists(temp_audio):
                    temp_files.append(temp_audio)
                    _to_wav(temp_audio, temp_wav)
                elif video_file and os.path.exists(video_file):
                    _to_wav(video_file, temp_wav)
            segments, info = _transcribe_with_whisper(temp_wav)
            transcript_segments = []
            for segment in segments:
                transcript_segments.append({
                    "start": segment.start,
                    "duration": segment.end - segment.start,
                    "text": segment.text.strip(),
                    "score": 0.0
                })
            for f in temp_files:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
            return transcript_segments
        except Exception as e2:
            print(f"Failed to transcribe video: {e2}")
        return []