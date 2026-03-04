import argparse
import json
import os
import subprocess
import sys

from . import config
from .analysis import analyze_transcript_with_ai, generate_publishing_metadata
from .media import (
    ambil_most_replayed,
    coba_masukkan_ffmpeg_ke_path,
    cek_dependensi,
    extract_video_id,
    ffmpeg_tersedia,
    get_duration,
    get_model_size,
    get_transcript_segments,
    process_single_clip,
)


def parse_args():
    parser = argparse.ArgumentParser(prog="mindcut")
    parser.add_argument("--url", help="YouTube URL (watch/shorts/youtu.be)")
    parser.add_argument(
        "--crop",
        choices=["default", "split_left", "split_right", "face"],
        help="Crop mode",
    )
    parser.add_argument(
        "--subtitle",
        choices=["y", "n"],
        help="Enable auto subtitle (y/n)",
    )
    parser.add_argument(
        "--whisper-model", dest="whisper_model", help="Faster-Whisper model"
    )
    parser.add_argument(
        "--subtitle-font",
        dest="subtitle_font",
        help="Subtitle font name (e.g., Poppins)",
    )
    parser.add_argument(
        "--subtitle-fontsdir",
        dest="subtitle_fontsdir",
        help="Folder containing .ttf/.otf fonts",
    )
    parser.add_argument(
        "--subtitle-location",
        dest="subtitle_location",
        choices=["center", "bottom"],
        help="Subtitle placement: center or bottom",
    )
    parser.add_argument(
        "--ratio",
        choices=["9:16", "1:1", "16:9", "original"],
        help="Output ratio preset",
    )
    parser.add_argument(
        "--check", action="store_true", help="Check dependencies then exit"
    )
    parser.add_argument(
        "--no-update-ytdlp", action="store_true", help="Skip auto-update yt-dlp"
    )
    parser.add_argument(
        "--analysis-mode",
        dest="analysis_mode",
        choices=["heatmap", "ai", "combined"],
        help="Analysis mode: heatmap (default), ai (AI transcript analysis), or combined",
    )
    parser.add_argument(
        "--ai-api-url", dest="ai_api_url", help="AI API URL (OpenAI-compatible)"
    )
    parser.add_argument("--ai-model", dest="ai_model", help="AI model name")
    parser.add_argument("--ai-api-key", dest="ai_api_key", help="AI API key")
    parser.add_argument(
        "--ai-prompt", dest="ai_prompt", help="Custom prompt for AI segment scoring"
    )
    parser.add_argument(
        "--ai-metadata-prompt",
        dest="ai_metadata_prompt",
        help="Custom prompt for publishing metadata",
    )
    return parser.parse_args()


def main():
    """
    Main entry point of the application.
    """
    args = parse_args()
    cek_dependensi._args = args

    if args.whisper_model:
        config.WHISPER_MODEL = args.whisper_model
    if args.subtitle_font:
        config.SUBTITLE_FONT = args.subtitle_font
    if args.subtitle_fontsdir:
        config.SUBTITLE_FONTS_DIR = args.subtitle_fontsdir
    if args.subtitle_location:
        config.SUBTITLE_LOCATION = args.subtitle_location
    if args.ratio:
        config.set_ratio_preset(args.ratio)
    if (
        args.ai_api_url
        or args.ai_model
        or args.ai_api_key
        or args.ai_prompt
        or args.ai_metadata_prompt
    ):
        config.set_ai_config(
            api_url=args.ai_api_url,
            model=args.ai_model,
            api_key=args.ai_api_key,
            segment_prompt=args.ai_prompt,
            metadata_prompt=args.ai_metadata_prompt,
        )

    if args.check:
        cek_dependensi(install_whisper=False)
        print("OK Basic dependencies OK.")
        return

    coba_masukkan_ffmpeg_ke_path()
    if not ffmpeg_tersedia():
        print("FFmpeg not found. Please install FFmpeg and ensure it is in PATH.")
        return

    crop_mode = args.crop
    crop_desc = None
    if crop_mode:
        crop_desc = {
            "default": "Default center crop",
            "split_left": "Split crop (bottom-left facecam)",
            "split_right": "Split crop (bottom-right facecam)",
            "face": "Face tracking crop (auto center)",
        }[crop_mode]

    subtitle_choice = args.subtitle
    if subtitle_choice:
        use_subtitle = subtitle_choice == "y"
    else:
        use_subtitle = None

    link = args.url

    if crop_mode is None or use_subtitle is None or not link:
        print("\n=== Crop Mode ===")
        print("1. Default (center crop)")
        print("2. Split 1 (top: center, bottom: bottom-left (facecam))")
        print("3. Split 2 (top: center, bottom: bottom-right ((facecam))")
        print("4. Face tracking (auto center)")

        while crop_mode is None:
            choice = input("\nSelect crop mode (1-4): ").strip()
            if choice == "1":
                crop_mode = "default"
                crop_desc = "Default center crop"
                break
            if choice == "2":
                crop_mode = "split_left"
                crop_desc = "Split crop (bottom-left facecam)"
                break
            if choice == "3":
                crop_mode = "split_right"
                crop_desc = "Split crop (bottom-right facecam)"
                break
            if choice == "4":
                crop_mode = "face"
                crop_desc = "Face tracking crop (auto center)"
                break
            print("Invalid choice. Please enter 1, 2, 3, or 4.")

        print(f"Selected: {crop_desc}")

        print("\n=== Auto Subtitle ===")
        print(
            f"Available model: {config.WHISPER_MODEL} (~{get_model_size(config.WHISPER_MODEL)})"
        )
        while use_subtitle is None:
            subtitle_choice = (
                input("Add auto subtitle using Faster-Whisper? (y/n): ").strip().lower()
            )
            if subtitle_choice in ["y", "yes"]:
                use_subtitle = True
            elif subtitle_choice in ["n", "no"]:
                use_subtitle = False
            else:
                print("Invalid choice. Please enter y or n.")

        if use_subtitle:
            print(
                f"OK Subtitle enabled (Model: {config.WHISPER_MODEL}, Bahasa Indonesia)"
            )
        else:
            print("NO Subtitle disabled")

        print()

        cek_dependensi(install_whisper=use_subtitle)

        if not link:
            link = input("Link YT: ").strip()
    else:
        cek_dependensi(install_whisper=use_subtitle)

    video_id = extract_video_id(link)

    if not video_id:
        print("Invalid YouTube link.")
        return

    # Determine analysis mode
    analysis_mode = "heatmap"
    if hasattr(args, "analysis_mode") and args.analysis_mode:
        analysis_mode = args.analysis_mode

    print(f"Analysis mode: {analysis_mode}")

    if analysis_mode == "ai":
        # AI analysis mode
        print("Fetching video metadata...")
        try:
            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--skip-download",
                "-J",
                f"https://youtu.be/{video_id}",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print("Failed to get video metadata")
                video_title = ""
                video_description = ""
            else:
                raw = json.loads(res.stdout)
                item = (
                    raw["entries"][0]
                    if isinstance(raw, dict) and "entries" in raw and raw.get("entries")
                    else raw
                )
                video_title = item.get("title", "")
                video_description = item.get("description", "")
        except Exception as e:
            print(f"Error getting video metadata: {e}")
            video_title = ""
            video_description = ""

        print("Extracting transcript segments...")
        transcript_segments = get_transcript_segments(video_id)

        if not transcript_segments:
            print("No transcript segments found. Falling back to heatmap analysis.")
            heatmap_data = ambil_most_replayed(video_id)
            if not heatmap_data:
                print("No high-engagement segments found.")
                return
            segments_to_process = heatmap_data
        else:
            print(f"Found {len(transcript_segments)} transcript segments.")
            print("Analyzing with AI...")
            heatmap_data = ambil_most_replayed(video_id)
            ai_segments = analyze_transcript_with_ai(
                transcript_segments,
                video_title,
                video_description,
                custom_prompt=args.ai_prompt or "",
                heatmap_segments=heatmap_data,
            )

            # Get heatmap data for comparison
            print(f"Found {len(heatmap_data)} heatmap segments.")

            # Combine heatmap and AI analysis
            segments_to_process = ai_segments

            if not segments_to_process:
                print("No segments found after AI analysis.")
                return

        print(f"Using {len(segments_to_process)} segments for clip generation.")

    elif analysis_mode == "combined":
        # Combined mode: use both heatmap and AI analysis
        heatmap_data = ambil_most_replayed(video_id)
        print(f"Found {len(heatmap_data)} heatmap segments.")

        # Get transcript for AI analysis
        transcript_segments = get_transcript_segments(video_id)
        if transcript_segments:
            print(f"Found {len(transcript_segments)} transcript segments.")
            ai_segments = analyze_transcript_with_ai(
                transcript_segments,
                "",
                "",
                custom_prompt=args.ai_prompt or "",
                heatmap_segments=heatmap_data,
            )
            segments_to_process = ai_segments
        else:
            segments_to_process = heatmap_data

        if not segments_to_process:
            print("No segments found.")
            return

    else:
        # Default heatmap mode
        heatmap_data = ambil_most_replayed(video_id)

        if not heatmap_data:
            print("No high-engagement segments found.")
            return

        segments_to_process = heatmap_data

    if analysis_mode in ("ai", "combined") and (
        args.ai_metadata_prompt or config.AI_METADATA_PROMPT
    ):
        try:
            metadata = generate_publishing_metadata(
                transcript_segments if "transcript_segments" in locals() else [],
                video_title if "video_title" in locals() else "",
                video_description if "video_description" in locals() else "",
                heatmap_segments=heatmap_data if "heatmap_data" in locals() else [],
                candidate_segments=segments_to_process,
                custom_prompt=args.ai_metadata_prompt or "",
            )
            if metadata:
                print("\nPublishing metadata (JSON):")
                print(json.dumps(metadata, ensure_ascii=False, indent=2))
        except Exception:
            pass

    print(f"Found {len(segments_to_process)} segments to process.")

    total_duration = get_duration(video_id)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print(
        f"Processing clips with {config.PADDING}s pre-padding "
        f"and {config.PADDING}s post-padding."
    )
    print(f"Using crop mode: {crop_desc}")

    success_count = 0

    for item in segments_to_process:
        if success_count >= config.MAX_CLIPS:
            break

        if process_single_clip(
            video_id, item, success_count + 1, total_duration, crop_mode, use_subtitle
        ):
            success_count += 1

    print(
        f"Finished processing. "
        f"{success_count} clip(s) successfully saved to '{config.OUTPUT_DIR}'."
    )
