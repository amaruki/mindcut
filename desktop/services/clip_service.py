import os
import glob
import threading
from kivy.clock import Clock
from core import config, media


def get_gallery():
    """Returns a list of clips from the clips/ directory."""
    clips_dir = config.OUTPUT_DIR
    if not os.path.exists(clips_dir):
        return []

    mp4s = glob.glob(os.path.join(clips_dir, "**", "*.mp4"), recursive=True)
    results = []
    for m in mp4s:
        base = os.path.basename(m)
        abs_m = os.path.abspath(m)
        results.append(
            {
                "filename": base,
                "path": abs_m,
                "size_bytes": os.path.getsize(abs_m),
                "url": f"file:///{abs_m.replace(os.sep, '/')}",
            }
        )
    results.sort(key=lambda x: os.path.getmtime(x["path"]), reverse=True)
    return results


def delete_clip(path):
    if os.path.exists(path):
        os.remove(path)
        # also try to remove .txt / .json metadata if exists
        base = os.path.splitext(path)[0]
        for ext in [".txt", ".json", ".jpg"]:
            if os.path.exists(base + ext):
                os.remove(base + ext)
        return True
    return False


# ----------------- Threaded Wrappers -----------------


def run_scan(url, mode, crop_target, on_progress, on_complete):
    """Runs the scan process in a background thread."""

    def threaded_scan():
        try:
            # Fake progress for skeleton - real integration later
            Clock.schedule_once(lambda dt: on_progress(10, "Extracting video ID..."))
            video_id = media.youtube.extract_video_id(url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")

            Clock.schedule_once(
                lambda dt: on_progress(50, "Fetching heatmap/segments...")
            )
            import time

            time.sleep(1)  # simulate work

            # Dummy result
            segments = [
                {
                    "start": 10,
                    "end": 20,
                    "score": 0.95,
                    "text": "Dummy Segment 1",
                    "reason": "Heatmap peak",
                },
                {
                    "start": 30,
                    "end": 45,
                    "score": 0.88,
                    "text": "Dummy Segment 2",
                    "reason": "AI picked",
                },
            ]

            Clock.schedule_once(lambda dt: on_progress(100, "Done"))
            Clock.schedule_once(
                lambda dt: on_complete({"success": True, "segments": segments})
            )
        except Exception as e:
            err = str(e)
            Clock.schedule_once(
                lambda dt, error=err: on_complete({"success": False, "error": error})
            )

    thread = threading.Thread(target=threaded_scan)
    thread.daemon = True
    thread.start()


def run_clip(url, segments, crop_target, on_progress, on_complete):
    """Runs the clip generation in a background thread."""

    def threaded_clip():
        try:
            total = len(segments)
            for i, seg in enumerate(segments):
                stage = f"Processing clip {i + 1} of {total}"
                Clock.schedule_once(
                    lambda dt, s=stage: on_progress((i / total) * 100, s)
                )
                import time

                time.sleep(1)  # simulate work

            Clock.schedule_once(lambda dt: on_progress(100, "Done"))
            Clock.schedule_once(lambda dt: on_complete({"success": True}))
        except Exception as e:
            err = str(e)
            Clock.schedule_once(
                lambda dt, error=err: on_complete({"success": False, "error": error})
            )

    thread = threading.Thread(target=threaded_clip)
    thread.daemon = True
    thread.start()
