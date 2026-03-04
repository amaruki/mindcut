import json
import re
import time
from dataclasses import asdict, dataclass, field

import requests

from .. import config
from ..media.summary import summarize_heatmap_segments, summarize_transcript_segments

"""
Publishing Metadata Generator - Improved Algorithm
Generates multi-platform metadata for short-form clips from long-form video context.
"""

MAX_RETRIES = 3
REQUEST_TIMEOUT = 45

PLATFORM_SPECS = {
    "youtube_shorts": {
        "title_max": 100,
        "description_max": 500,
        "hashtag_count": 3,     # YouTube recommends <=3 for Shorts
        "tag_count": 10,
        "allow_emojis": True,
        "cta": "Subscribe for more!",
    },
    "tiktok": {
        "title_max": 150,
        "description_max": 2200,
        "hashtag_count": 8,
        "tag_count": 0,     # TikTok uses hashtags only, no separate tags
        "allow_emojis": True,
        "cta": "Follow for more",
    },
    "instagram_reels": {
        "title_max": 125,
        "description_max": 2200,
        "hashtag_count": 10,
        "tag_count": 0,
        "allow_emojis": True,
        "cta": "Save this!",
    },
    "facebook_reels": {
        "title_max": 255,
        "description_max": 500,
        "hashtag_count": 5,
        "tag_count": 0,
        "allow_emojis": False,
        "cta": "Share with someone who needs this.",
    },
}


@dataclass
class ClipMetadata:
    # Core (platform-agnostic)
    core_title: str = ""
    core_description: str = ""
    hook: str = ""
    thumbnail_text: str = ""
    category: str = ""
    content_tone: str = ""     # e.g. "educational", "entertaining", "controversial"
    language: str = "en"

    # SEO
    tags: list = field(default_factory=list)
    hashtags: list = field(default_factory=list)
    keywords: list = field(default_factory=list)

    # Timestamps (for video chapters / clip suggestions)
    timestamps: list = field(default_factory=list)  # [{start, end, label, reason}]

    # A/B variants
    title_variants: list = field(default_factory=list)  # 3 alternatives
    hook_variants: list = field(default_factory=list)  # 3 alternatives

    # Per-platform overrides
    platforms: dict = field(default_factory=dict)  # platform -> {title, description, hashtags, cta}

    # Publishing guidance
    best_publish_time: str = ""
    publish_notes: str = ""
    seo_score: float = 0.0   # estimated 0-1 based on completeness
    confidence: float = 0.0   # AI confidence in the suggestions

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_json(raw: str) -> dict | list | None:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        m = re.search(pattern, raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                continue
    return None


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _clean_hashtag(tag: str) -> str:
    t = tag.strip()
    if not t:
        return ""
    t = t.replace("#", "")
    t = re.sub(r"[^0-9A-Za-z_]+", "", t)
    if not t:
        return ""
    return f"#{t}"


def _estimate_seo_score(meta: ClipMetadata) -> float:
    score = 0.0
    if meta.core_title:
        score += 0.25
    if meta.core_description:
        score += 0.25
    if meta.tags:
        score += 0.2
    if meta.hashtags:
        score += 0.2
    if meta.title_variants:
        score += 0.1
    return round(score, 3)


def _build_context(
    transcript_segments: list[dict],
    video_title: str,
    video_description: str,
    heatmap_segments: list[dict],
    candidate_segments: list[dict],
    max_segments: int = 6,
) -> str:
    transcript_summary = summarize_transcript_segments(transcript_segments, limit=max_segments, include_text=True)
    heatmap_summary = summarize_heatmap_segments(heatmap_segments, limit=max_segments)
    candidate_summary = summarize_transcript_segments(candidate_segments, limit=max_segments, include_text=True)

    return f"""
VIDEO TITLE: {video_title}
VIDEO DESCRIPTION: {video_description}

TRANSCRIPT SEGMENTS (sample):
{transcript_summary}

HEATMAP SEGMENTS (sample):
{heatmap_summary}

CANDIDATE SEGMENTS (sample):
{candidate_summary}
""".strip()


def _call_ai_metadata(prompt: str) -> dict | None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.AI_API_KEY}",
    }
    payload = {
        "model": config.discover_ai_model(),
        "messages": [
            {"role": "system", "content": "You are a helpful publishing strategist"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
    }

    for _ in range(MAX_RETRIES):
        try:
            resp = requests.post(config.get_ai_chat_url(), headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            parsed = _safe_json(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            time.sleep(1)
    return None


def _sanitize(raw: dict, specs: dict = PLATFORM_SPECS) -> ClipMetadata:
    meta = ClipMetadata()
    if not isinstance(raw, dict):
        return meta

    meta.core_title = str(raw.get("core_title", "") or "")
    meta.core_description = str(raw.get("core_description", "") or "")
    meta.hook = str(raw.get("hook", "") or "")
    meta.thumbnail_text = str(raw.get("thumbnail_text", "") or "")
    meta.category = str(raw.get("category", "") or "")
    meta.content_tone = str(raw.get("content_tone", "") or "")
    meta.language = str(raw.get("language", "en") or "en")

    meta.tags = list(raw.get("tags", []) or [])[:20]
    meta.hashtags = list(raw.get("hashtags", []) or [])[:20]
    meta.keywords = list(raw.get("keywords", []) or [])[:20]

    meta.timestamps = list(raw.get("timestamps", []) or [])[:10]

    meta.title_variants = list(raw.get("title_variants", []) or [])[:5]
    meta.hook_variants = list(raw.get("hook_variants", []) or [])[:5]

    meta.platforms = dict(raw.get("platforms", {}) or {})
    meta.best_publish_time = str(raw.get("best_publish_time", "") or "")
    meta.publish_notes = str(raw.get("publish_notes", "") or "")
    meta.confidence = float(raw.get("confidence", 0.0) or 0.0)

    # Clean hashtags & per-platform limits
    meta.hashtags = [h for h in (_clean_hashtag(h) for h in meta.hashtags) if h]
    for platform, data in meta.platforms.items():
        spec = specs.get(platform)
        if not spec or not isinstance(data, dict):
            continue
        title = str(data.get("title", "") or "")
        desc = str(data.get("description", "") or "")
        hashtags = [h for h in (_clean_hashtag(h) for h in data.get("hashtags", []) or []) if h]

        data["title"] = _truncate(title, spec["title_max"])
        data["description"] = _truncate(desc, spec["description_max"])
        data["hashtags"] = hashtags[:spec["hashtag_count"]]
        data["cta"] = str(data.get("cta", spec.get("cta", "")) or spec.get("cta", ""))
        data["tags"] = list(data.get("tags", []) or [])[:spec["tag_count"]]

        meta.platforms[platform] = data

    # Clamp lengths
    meta.core_title = _truncate(meta.core_title, 120)
    meta.core_description = _truncate(meta.core_description, 800)
    meta.thumbnail_text = _truncate(meta.thumbnail_text, 60)

    meta.seo_score = _estimate_seo_score(meta)
    return meta


def _heuristic_metadata(
    transcript_segments: list[dict],
    video_title: str,
    video_description: str,
) -> ClipMetadata:
    meta = ClipMetadata()
    meta.core_title = (video_title or "")[:90]
    meta.core_description = (video_description or "")[:350]
    meta.hook = (video_title or "")[:70]
    meta.thumbnail_text = (video_title or "")[:40]
    meta.category = "general"
    meta.content_tone = "informative"
    meta.tags = []
    meta.hashtags = []
    meta.keywords = []
    meta.seo_score = _estimate_seo_score(meta)
    meta.confidence = 0.2
    return meta


def generate_publishing_metadata(
    transcript_segments: list[dict],
    video_title: str,
    video_description: str,
    heatmap_segments: list[dict] | None = None,
    candidate_segments: list[dict] | None = None,
    platforms: list[str] | None = None,
    custom_prompt: str = "",
) -> dict:
    """
    Generate metadata suggestions for publishing short clips.
    Returns a dict ready for JSON output.
    """
    heatmap_segments = heatmap_segments or []
    candidate_segments = candidate_segments or []
    platforms = platforms or ["youtube_shorts", "tiktok", "instagram_reels"]

    extra = (custom_prompt or config.AI_METADATA_PROMPT or "").strip()
    context = _build_context(
        transcript_segments,
        video_title,
        video_description,
        heatmap_segments,
        candidate_segments,
    )

    prompt = f"""
You are a multi-platform short-form video publishing strategist.
Given the video context below, generate publishing metadata for short clips.

Return ONLY valid JSON with this structure:
{{
  "core_title": "...",
  "core_description": "...",
  "hook": "...",
  "thumbnail_text": "...",
  "category": "...",
  "content_tone": "...",
  "language": "en",
  "tags": ["..."],
  "hashtags": ["..."],
  "keywords": ["..."],
  "timestamps": [{{"start": 0, "end": 30, "label": "...", "reason": "..."}}],
  "title_variants": ["..."],
  "hook_variants": ["..."],
  "platforms": {{
    "youtube_shorts": {{"title": "...", "description": "...", "hashtags": ["..."], "tags": ["..."], "cta": "..."}},
    "tiktok": {{"title": "...", "description": "...", "hashtags": ["..."], "cta": "..."}},
    "instagram_reels": {{"title": "...", "description": "...", "hashtags": ["..."], "cta": "..."}}
  }},
  "best_publish_time": "...",
  "publish_notes": "...",
  "confidence": 0.0
}}

Video Context:
{context}

Target platforms: {', '.join(platforms)}
{extra}
""".strip()

    if not config.AI_API_KEY:
        print("Warning: AI_API_KEY not set. Using heuristic metadata generation.")
        return _heuristic_metadata(transcript_segments, video_title, video_description).to_dict()

    raw = _call_ai_metadata(prompt)
    if not raw:
        return _heuristic_metadata(transcript_segments, video_title, video_description).to_dict()

    return _sanitize(raw).to_dict()