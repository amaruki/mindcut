from . import config
from .analysis import (
    ClipCandidate,
    ClipMetadata,
    analyze_transcript_with_ai,
    log_clip_performance,
    generate_publishing_metadata,
)
from .cli import main, parse_args
from .media import (
    ambil_most_replayed,
    build_cover_scale_crop_vf,
    build_cover_scale_vf,
    build_face_crop_vf,
    build_subtitle_force_style,
    cek_dependensi,
    coba_masukkan_ffmpeg_ke_path,
    detect_face_center,
    download_video,
    escape_subtitles_filter_dir,
    escape_subtitles_filter_path,
    extract_video_id,
    ffmpeg_tersedia,
    format_timestamp,
    generate_subtitle,
    get_duration,
    get_model_size,
    get_split_heights,
    get_transcript_segments,
    process_single_clip,
    summarize_heatmap_segments,
    summarize_transcript_segments,
)

_CONFIG_EXPORTS = [
    "AI_API_KEY",
    "AI_API_URL",
    "AI_METADATA_PROMPT",
    "AI_MODEL",
    "AI_SEGMENT_PROMPT",
    "BOTTOM_HEIGHT",
    "COOKIES_BROWSER",
    "MAX_CLIPS",
    "MAX_DURATION",
    "MAX_WORKERS",
    "MIN_SCORE",
    "OUT_HEIGHT",
    "OUT_WIDTH",
    "OUTPUT_DIR",
    "OUTPUT_RATIO",
    "PADDING",
    "SUBTITLE_FONT",
    "SUBTITLE_FONTS_DIR",
    "SUBTITLE_LOCATION",
    "TOP_HEIGHT",
    "USE_SUBTITLE",
    "WHISPER_MODEL",
]


def _sync_config():
    for name in _CONFIG_EXPORTS:
        globals()[name] = getattr(config, name)


def set_ai_config(
    api_url=None,
    model=None,
    api_key=None,
    segment_prompt=None,
    metadata_prompt=None,
    cookies_browser=None,
):
    config.set_ai_config(
        api_url=api_url,
        model=model,
        api_key=api_key,
        segment_prompt=segment_prompt,
        metadata_prompt=metadata_prompt,
        cookies_browser=cookies_browser,
    )
    _sync_config()


def set_ratio_preset(preset):
    config.set_ratio_preset(preset)
    _sync_config()


_sync_config()

__all__ = [
    "AI_API_KEY",
    "AI_API_URL",
    "AI_METADATA_PROMPT",
    "AI_MODEL",
    "AI_SEGMENT_PROMPT",
    "BOTTOM_HEIGHT",
    "COOKIES_BROWSER",
    "MAX_CLIPS",
    "MAX_DURATION",
    "MAX_WORKERS",
    "MIN_SCORE",
    "OUT_HEIGHT",
    "OUT_WIDTH",
    "OUTPUT_DIR",
    "OUTPUT_RATIO",
    "PADDING",
    "SUBTITLE_FONT",
    "SUBTITLE_FONTS_DIR",
    "SUBTITLE_LOCATION",
    "TOP_HEIGHT",
    "USE_SUBTITLE",
    "WHISPER_MODEL",
    "ClipCandidate",
    "ClipMetadata",
    "ambil_most_replayed",
    "analyze_transcript_with_ai",
    "log_clip_performance",
    "build_cover_scale_crop_vf",
    "build_cover_scale_vf",
    "build_face_crop_vf",
    "build_subtitle_force_style",
    "cek_dependensi",
    "coba_masukkan_ffmpeg_ke_path",
    "config",
    "detect_face_center",
    "download_video",
    "escape_subtitles_filter_dir",
    "escape_subtitles_filter_path",
    "extract_video_id",
    "ffmpeg_tersedia",
    "format_timestamp",
    "generate_publishing_metadata",
    "generate_subtitle",
    "get_duration",
    "get_model_size",
    "get_split_heights",
    "get_transcript_segments",
    "main",
    "parse_args",
    "process_single_clip",
    "set_ai_config",
    "set_ratio_preset",
    "summarize_heatmap_segments",
    "summarize_transcript_segments",
]
