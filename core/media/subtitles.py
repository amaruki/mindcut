import os

from .. import config
from .transcribe import get_model_size


def escape_subtitles_filter_path(path):
    abs_path = os.path.abspath(path)
    return abs_path.replace("\\", "/").replace(":", "\\:")


def escape_subtitles_filter_dir(path):
    abs_path = os.path.abspath(path)
    return abs_path.replace("\\", "/").replace(":", "\\:")


def build_subtitle_force_style():
    alignment = "2" if config.SUBTITLE_LOCATION == "bottom" else "5"
    margin_v = "40" if config.SUBTITLE_LOCATION == "bottom" else "0"
    return (
        f"FontName={config.SUBTITLE_FONT},FontSize=12,Bold=1,"
        f"PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
        f"BorderStyle=1,Outline=2,Shadow=1,"
        f"Alignment={alignment},MarginV={margin_v}"
    )


def generate_subtitle(video_file, subtitle_file, event_hook=None):
    """
    Generate word-by-word subtitle file using Faster-Whisper.
    Uses word-level timestamps for tight sync with audio.
    Returns True if successful, False otherwise.
    """
    from faster_whisper import WhisperModel

    def load_and_transcribe():
        if callable(event_hook):
            try:
                event_hook("stage", {"stage": "subtitle_model_load"})
            except Exception:
                pass
        print(f"  Loading Faster-Whisper model '{config.WHISPER_MODEL}'...")
        print(f"  (If this is first time, downloading ~{get_model_size(config.WHISPER_MODEL)}...)")
        model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        print("  OK Model loaded. Transcribing audio with word-level timestamps...")
        if callable(event_hook):
            try:
                event_hook("stage", {"stage": "subtitle_transcribe"})
            except Exception:
                pass
        segments, info = model.transcribe(
            video_file,
            language="en",
            word_timestamps=True,
        )
        return segments

    try:
        segments = load_and_transcribe()
    except Exception as e:
        msg = str(e)
        if os.name == "nt" and "WinError 1314" in msg:
            print(f"  Failed to generate subtitle: {msg}")
            print("  Windows kamu kelihatan tidak mengizinkan symlink (HuggingFace cache).")
            print("  Retrying sekali lagi (biasanya langsung beres setelah fallback cache aktif)...")
            try:
                segments = load_and_transcribe()
            except Exception as e2:
                print(f"  Failed to generate subtitle: {str(e2)}")
                return False
        else:
            print(f"  Failed to generate subtitle: {msg}")
            return False

    if callable(event_hook):
        try:
            event_hook("stage", {"stage": "subtitle_write"})
        except Exception:
            pass

    # Collect all words with timestamps from all segments
    all_words = []
    for segment in segments:
        if segment.words:
            for w in segment.words:
                word_text = w.word.strip()
                if word_text:
                    all_words.append({
                        "start": w.start,
                        "end": w.end,
                        "text": word_text,
                    })
        else:
            # Fallback: if no word-level timestamps, use segment-level
            text = segment.text.strip()
            if text:
                all_words.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": text,
                })

    if not all_words:
        print("  No words detected in audio.")
        return False

    # Group words into small chunks (2-3 words each) for word-by-word display
    WORDS_PER_CHUNK = 3
    chunks = []
    for i in range(0, len(all_words), WORDS_PER_CHUNK):
        group = all_words[i:i + WORDS_PER_CHUNK]
        chunk_text = " ".join(w["text"] for w in group)
        chunk_start = group[0]["start"]
        chunk_end = group[-1]["end"]
        chunks.append({
            "start": chunk_start,
            "end": chunk_end,
            "text": chunk_text,
        })

    print(f"  Writing {len(chunks)} subtitle chunks ({len(all_words)} words)...")
    with open(subtitle_file, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks, start=1):
            start_time = format_timestamp(chunk["start"])
            end_time = format_timestamp(chunk["end"])
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{chunk['text']}\n\n")

    return True


def format_timestamp(seconds):
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"