import json
import re
import subprocess
import sys

import requests

from .. import config


def extract_video_id(url):
    """
    Extract the YouTube video ID from a given URL.
    Supports standard YouTube URLs, shortened URLs, and Shorts URLs.
    """
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path[1:]

    if parsed.hostname in ("youtube.com", "www.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/")[2]

    return None


def _merge_heatmap_segments(raw_segments, min_duration=15, gap_tolerance=2.0):
    """
    Merge adjacent heatmap points into longer segments.
    YouTube heatmap points are typically ~4s each; this combines nearby
    high-score points into clip-length segments (at least min_duration seconds).
    """
    if not raw_segments:
        return []

    # Sort by start time for merging
    by_start = sorted(raw_segments, key=lambda x: x["start"])

    merged = []
    cur = {
        "start": by_start[0]["start"],
        "end": by_start[0]["start"] + by_start[0]["duration"],
        "score": by_start[0]["score"],
        "count": 1,
    }

    for seg in by_start[1:]:
        seg_end = seg["start"] + seg["duration"]
        # Merge if this point is adjacent or overlapping (within gap_tolerance)
        if seg["start"] <= cur["end"] + gap_tolerance:
            cur["end"] = max(cur["end"], seg_end)
            cur["score"] = max(cur["score"], seg["score"])
            cur["count"] += 1
        else:
            merged.append(cur)
            cur = {
                "start": seg["start"],
                "end": seg_end,
                "score": seg["score"],
                "count": 1,
            }
    merged.append(cur)

    # Filter by minimum duration and convert to output format
    results = []
    for m in merged:
        dur = m["end"] - m["start"]
        if dur < min_duration:
            continue
        results.append(
            {
                "start": m["start"],
                "duration": min(dur, config.MAX_DURATION),
                "score": m["score"],
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def ambil_most_replayed(video_id):
    """
    Fetch and parse YouTube 'Most Replayed' heatmap data using yt-dlp, falling back to manual scrape.
    Returns a list of high-engagement segments (merged into clip-length chunks).
    """
    print("Reading YouTube heatmap data...")

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "-J",
        "--ignore-no-formats-error",
        f"https://www.youtube.com/watch?v={video_id}",
    ]

    def parse_heatmap_res(stdout_text):
        raw = json.loads(stdout_text)
        item = raw["entries"][0] if "entries" in raw and raw.get("entries") else raw
        heatmap = item.get("heatmap")
        if heatmap:
            raw_points = []
            for point in heatmap:
                start = point.get("start_time")
                end = point.get("end_time")
                score = point.get("value")
                if start is not None and end is not None and score is not None:
                    if score >= config.MIN_SCORE:
                        dur = end - start
                        raw_points.append(
                            {"start": start, "duration": dur, "score": score}
                        )
            if raw_points:
                return _merge_heatmap_segments(raw_points)
        return None

    if config.get_cookie_args():
        cmd_cookies = cmd + config.get_cookie_args()
        try:
            res = subprocess.run(
                cmd_cookies, capture_output=True, text=True, timeout=30
            )
            if res.returncode == 0:
                results = parse_heatmap_res(res.stdout)
                if results:
                    print(
                        f"Successfully fetched heatmap using yt-dlp with cookies ({len(results)} segments)."
                    )
                    return results
            else:
                print(
                    "Warning: yt-dlp heatmap fetch with cookies failed. Retrying without cookies."
                )
        except Exception as e:
            print(f"Warning: yt-dlp heatmap fetch with cookies raised exception: {e}")

    # Retry without cookies
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            results = parse_heatmap_res(res.stdout)
            if results:
                print(
                    f"Successfully fetched heatmap using yt-dlp without cookies ({len(results)} segments)."
                )
                return results
    except Exception as e:
        print(f"Warning: yt-dlp heatmap fetch without cookies failed: {e}")

    # Fallback to direct request
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"User-Agent": "Mozilla/5.0"}

    print("Falling back to manual HTML scraping for heatmap...")
    try:
        html = requests.get(url, headers=headers, timeout=20).text
    except Exception:
        return []

    match = re.search(
        r'"markers":\s*(\[.*?\])\s*,\s*"?markersMetadata"?', html, re.DOTALL
    )

    if not match:
        return []

    try:
        markers = json.loads(match.group(1).replace('\\"', '"'))
    except Exception:
        return []

    raw_points = []

    for marker in markers:
        if "heatMarkerRenderer" in marker:
            marker = marker["heatMarkerRenderer"]

        try:
            score = float(marker.get("intensityScoreNormalized", 0))
            if score >= config.MIN_SCORE:
                raw_points.append(
                    {
                        "start": float(marker["startMillis"]) / 1000,
                        "duration": float(marker["durationMillis"]) / 1000,
                        "score": score,
                    }
                )
        except Exception:
            continue

    return _merge_heatmap_segments(raw_points)


def download_video(video_id, output_path, progress_hook=None):
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-ipv4",
        "--newline",
        "--no-warnings",
        "--ignore-no-formats-error",
        # Optimize performance
        "--concurrent-fragments",
        "5",
        "--http-chunk-size",
        "10M",
        "--merge-output-format",
        "mp4",
        "-f",
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "-o",
        output_path,
        f"https://youtu.be/{video_id}",
    ]

    def _run_cmd(cmd_args):
        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in process.stdout:
            # Parse yt-dlp output for progress
            if progress_hook and "[download]" in line and "%" in line:
                match = re.search(
                    r"\[download\]\s+([\d\.]+)%\s+of.*?(?:at\s+([^\s]+))?", line
                )
                if match:
                    try:
                        pct = float(match.group(1))
                        speed = match.group(2) if match.group(2) else ""
                        progress_hook({"pct": pct, "speed": speed})
                    except ValueError:
                        pass

        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_args)

    cookie_args = config.get_cookie_args()
    if cookie_args:
        cmd_cookies = cmd + cookie_args
        try:
            _run_cmd(cmd_cookies)
            return output_path
        except subprocess.CalledProcessError:
            print(
                "Warning: Download with cookies failed. Retrying download WITHOUT cookies..."
            )

    try:
        _run_cmd(cmd)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Gagal download video (return_code={e.returncode})")

    return output_path


def get_duration(video_id):
    """
    Get video duration in seconds using yt-dlp metadata.
    """
    try:
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--skip-download",
            "-J",
            "--ignore-no-formats-error",
            f"https://youtu.be/{video_id}",
        ]

        def parse_duration_res(stdout_text):
            raw = json.loads(stdout_text)
            item = (
                raw["entries"][0]
                if isinstance(raw, dict) and "entries" in raw and raw.get("entries")
                else raw
            )
            return int(item.get("duration") or 0)

        cookie_args = config.get_cookie_args()
        if cookie_args:
            cmd_cookies = cmd + cookie_args
            res = subprocess.run(cmd_cookies, capture_output=True, text=True)
            if res.returncode == 0:
                return parse_duration_res(res.stdout)
            else:
                print(
                    "Warning: get_duration with cookies failed. Retrying without cookies."
                )

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return 0
        return parse_duration_res(res.stdout)
    except Exception:
        return 0
