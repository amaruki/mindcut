"""
Viral Clip Analyzer — Improved Algorithm v2
Identifies best timestamps from long-form video to cut into short-form clips.
(YouTube Shorts, TikTok, Instagram Reels)

Fixes applied:
  1.  Keyword bank expanded with content-type tiers (not just hype words)
  2.  Fusion weights loaded from a JSONL performance log; falls back to defaults
  3.  Legacy combine_heatmap_and_ai_analysis removed — use analyze_transcript_with_ai
  4.  Pre-filter cap changed from hard-24 to top-30% (min 8, max 40)
  5.  Duration scoring is now content-type aware
  6.  Segment merge uses word-overlap coherence guard
  7.  AI prompt enriched with channel/video metadata
  8.  Emotion scoring is graduated (mild / moderate / intense tiers)
  9.  NMS deduplication removes clips with >60% time overlap
 10.  _safe_json returns (result, was_repaired) tuple; callers log repairs
 11.  Speech-rate (words/sec) added as a heuristic dimension
 12.  Performance logging helper added for future weight tuning
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import requests

from .. import config
from ..media.summary import summarize_heatmap_segments, summarize_transcript_segments

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

IDEAL_CLIP_MIN_SEC = 15
IDEAL_CLIP_MAX_SEC = 90
MERGE_GAP_SEC = 2.5
MIN_VIRAL_SCORE = 0.50
MAX_SEGMENTS_PER_BATCH = 50

# Path where per-clip performance feedback is appended.
# Each line is JSON: {"predicted": float, "actual_views": int, "actual_retention": float, ...}
PERFORMANCE_LOG_PATH = Path(config.DATA_DIR) / "clip_performance.jsonl" if hasattr(config, "DATA_DIR") else None

# Default fusion weights (used when no performance log exists yet)
_DEFAULT_WEIGHTS = {
    "ai": 0.55,
    "heatmap": 0.25,
    "heuristic": 0.20,
    # fallback (no AI)
    "heatmap_fallback": 0.40,
    "heuristic_fallback": 0.60,
}

# Pre-filter: send top N% of candidates to AI (ratio-based, not hard count)
PRE_FILTER_RATIO = 0.30   # top 30 %
PRE_FILTER_MIN = 8        # never send fewer than this
PRE_FILTER_MAX = 40       # never send more than this

# NMS: suppress a lower-scored clip if it overlaps a higher-scored one by this ratio
NMS_OVERLAP_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# KEYWORD / EMOTION BANKS  (fix #1 + #8)
# ---------------------------------------------------------------------------

# Tiered by content style so educational/commentary clips aren't penalised
# for not using hype words.
_KEYWORD_WEIGHTS: dict[str, float] = {
    # ── Attention / scroll-stop ──────────────────────────────────────────
    "you won't believe": 0.20,
    "mind-blowing": 0.18,
    "shocking": 0.16,
    "incredible": 0.14,
    "unbelievable": 0.14,
    "insane": 0.13,
    "secret": 0.12,
    "nobody talks about": 0.15,
    "biggest mistake": 0.14,
    "wait for it": 0.13,
    "plot twist": 0.15,
    # ── Story / revelation ───────────────────────────────────────────────
    "the truth is": 0.13,
    "what actually happened": 0.12,
    "here's why": 0.11,
    "the real reason": 0.13,
    "turns out": 0.10,
    "i never told anyone": 0.15,
    "for the first time": 0.11,
    "this is why": 0.10,
    "here's the thing": 0.10,
    # ── Actionable / value ───────────────────────────────────────────────
    "how to": 0.10,
    "the trick is": 0.12,
    "just do this": 0.11,
    "most people don't know": 0.13,
    "this changed everything": 0.12,
    "step by step": 0.09,
    "the mistake everyone makes": 0.13,
    # ── Relatable / conversational (modern viral style) ──────────────────
    "not gonna lie": 0.09,
    "hear me out": 0.11,
    "this is wild": 0.12,
    "i can't believe": 0.10,
    "pov": 0.10,
    "no one prepared me": 0.13,
    "they don't want you to know": 0.14,
    "i tried it": 0.09,
    "spoiler": 0.10,
    # ── Engagement triggers ──────────────────────────────────────────────
    "what do you think": 0.09,
    "let me know": 0.08,
    "comment below": 0.08,
    "share this": 0.09,
    # ── Mild ─────────────────────────────────────────────────────────────
    "amazing": 0.07,
    "wow": 0.07,
    "epic": 0.07,
    "legendary": 0.07,
    "crazy": 0.06,
    "cool": 0.05,
    "interesting": 0.05,
}

# Graduated emotion scoring — each tier has a score ceiling (fix #8)
_EMOTION_TIERS: list[tuple[list[str], float]] = [
    # (keywords, score)
    (["terrified", "devastated", "heartbroken", "outraged", "furious", "obsessed"], 0.18),
    (["shocked", "disgusted", "ecstatic", "thrilled", "horrified", "amazed"], 0.13),
    (["surprised", "excited", "angry", "scared", "inspired", "frustrated"], 0.09),
    (["love", "hate", "fear", "sad", "funny", "happy", "nervous", "proud"], 0.05),
]


def _emotion_score(text: str) -> float:
    """Return graduated emotion score — higher intensity → higher score."""
    t = text.lower()
    for keywords, score in _EMOTION_TIERS:
        if any(w in t for w in keywords):
            return score
    return 0.0


# ---------------------------------------------------------------------------
# CONTENT-TYPE DETECTION  (fix #5)
# ---------------------------------------------------------------------------

_CONTENT_TYPE_SIGNALS: dict[str, list[str]] = {
    "comedy":      ["joke", "lol", "funny", "prank", "roast", "meme", "humor", "laugh", "hilarious"],
    "educational": ["explain", "how to", "tutorial", "learn", "tip", "strategy", "guide", "step", "because"],
    "reaction":    ["reacting", "first time", "watching", "oh my", "i can't", "did you see"],
    "commentary":  ["think about it", "here's the thing", "my opinion", "the real problem", "nobody talks"],
    "story":       ["so i was", "true story", "this happened", "back in", "i remember", "one day"],
}

_IDEAL_DURATION_BY_TYPE: dict[str, tuple[float, float]] = {
    "comedy":      (10, 45),
    "educational": (30, 90),
    "reaction":    (15, 60),
    "commentary":  (25, 75),
    "story":       (30, 80),
    "unknown":     (15, 90),
}


def _detect_content_type(text: str) -> str:
    t = text.lower()
    best, best_count = "unknown", 0
    for ctype, signals in _CONTENT_TYPE_SIGNALS.items():
        count = sum(1 for s in signals if s in t)
        if count > best_count:
            best, best_count = ctype, count
    return best


# ---------------------------------------------------------------------------
# ADAPTIVE FUSION WEIGHTS  (fix #2)
# ---------------------------------------------------------------------------

def _load_fusion_weights() -> dict:
    """
    Derive fusion weights from logged performance data if available.
    Falls back to defaults if the log is missing or too small (<20 entries).

    The log is a JSONL file where each line has:
        {"predicted": float, "ai": float, "heatmap": float, "heuristic": float,
         "actual_views": int, "actual_retention": float}

    We run a simple OLS-style average to find which signal correlates best
    with actual retention and rescale weights proportionally.
    """
    if not PERFORMANCE_LOG_PATH or not PERFORMANCE_LOG_PATH.exists():
        return _DEFAULT_WEIGHTS.copy()

    try:
        entries = []
        with PERFORMANCE_LOG_PATH.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        if len(entries) < 20:
            return _DEFAULT_WEIGHTS.copy()

        # Simple correlation proxy: mean absolute contribution to actual_retention
        def _corr(key: str) -> float:
            pairs = [(e[key], e["actual_retention"]) for e in entries if key in e and "actual_retention" in e]
            if not pairs:
                return 0.0
            xs, ys = zip(*pairs)
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            num = sum((x - mx) * (y - my) for x, y in pairs)
            den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
            return num / den if den else 0.0

        corr_ai        = max(0.01, _corr("ai"))
        corr_heatmap   = max(0.01, _corr("heatmap"))
        corr_heuristic = max(0.01, _corr("heuristic"))
        total = corr_ai + corr_heatmap + corr_heuristic

        weights = {
            "ai":        round(corr_ai / total, 3),
            "heatmap":   round(corr_heatmap / total, 3),
            "heuristic": round(corr_heuristic / total, 3),
        }
        # Fallback weights keep default ratio but renormalise
        hf_total = weights["heatmap"] + weights["heuristic"]
        weights["heatmap_fallback"]   = round(weights["heatmap"] / hf_total, 3)
        weights["heuristic_fallback"] = round(weights["heuristic"] / hf_total, 3)

        print(f"[weights] Loaded empirical fusion weights from {len(entries)} samples: {weights}")
        return weights

    except Exception as e:
        print(f"[weights] Failed to load performance log: {e}; using defaults")
        return _DEFAULT_WEIGHTS.copy()


def log_clip_performance(
    predicted_score: float,
    ai_score: float,
    heatmap_score: float,
    heuristic_score: float,
    actual_views: Optional[int] = None,
    actual_retention: Optional[float] = None,
    clip_id: Optional[str] = None,
) -> None:
    """
    Append one performance record to the JSONL log for future weight tuning.
    Call this after a published clip's analytics are available.
    """
    if not PERFORMANCE_LOG_PATH:
        return
    record = {
        "ts": time.time(),
        "clip_id": clip_id,
        "predicted": predicted_score,
        "ai": ai_score,
        "heatmap": heatmap_score,
        "heuristic": heuristic_score,
        "actual_views": actual_views,
        "actual_retention": actual_retention,
    }
    try:
        PERFORMANCE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PERFORMANCE_LOG_PATH.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[perf_log] Could not write performance log: {e}")


# ---------------------------------------------------------------------------
# DATACLASS
# ---------------------------------------------------------------------------

@dataclass
class ClipCandidate:
    segment_indices: list[int]
    start_time: float
    end_time: float
    duration: float
    text: str
    content_type: str = "unknown"

    # Scores (0.0–1.0 each)
    heuristic_score: float = 0.0
    heatmap_score: float = 0.0
    ai_score: float = 0.0
    final_score: float = 0.0

    # AI-enriched metadata
    hook_preview: str = ""
    clip_reason: str = ""
    suggested_clip_title: str = ""
    platform_fit: list[str] = field(default_factory=list)
    dimension_scores: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start_formatted"] = _fmt_time(self.start_time)
        d["end_formatted"] = _fmt_time(self.end_time)
        return d


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _safe_json(raw: str) -> tuple[list | dict | None, bool]:
    """
    Robustly extract JSON from a string that may contain extra text or truncation.
    Returns (parsed_result, was_repaired).  Callers should log when was_repaired=True.
    """
    raw = raw.strip()
    # Direct parse
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        pass
    # Extract embedded JSON
    for pattern in [r"\[[\s\S]*\]", r"\{[\s\S]*\}"]:
        m = re.search(pattern, raw)
        if m:
            try:
                return json.loads(m.group()), False
            except json.JSONDecodeError:
                continue
    # Repair truncated array
    arr_start = raw.find("[")
    if arr_start >= 0:
        fragment = raw[arr_start:]
        last_complete = fragment.rfind("}")
        if last_complete > 0:
            trimmed = fragment[:last_complete + 1].rstrip(", \n\r\t") + "]"
            try:
                result = json.loads(trimmed)
                if isinstance(result, list) and result:
                    return result, True   # ← repaired flag
            except json.JSONDecodeError:
                pass
    return None, False


# ---------------------------------------------------------------------------
# HEURISTIC SCORING  (fixes #1, #5, #8, #11)
# ---------------------------------------------------------------------------

def _heuristic_score(text: str, duration: float, content_type: str = "unknown") -> dict[str, float]:
    t = text.lower()
    words = t.split()

    # Keyword weight sum (cap at 0.35)
    keyword_score = 0.0
    for k, w in _KEYWORD_WEIGHTS.items():
        if k in t:
            keyword_score += w
    keyword_score = min(keyword_score, 0.35)

    # Graduated emotion score (fix #8)
    emo_score = _emotion_score(t)

    # Content-type-aware duration score (fix #5)
    ideal_min, ideal_max = _IDEAL_DURATION_BY_TYPE.get(content_type, _IDEAL_DURATION_BY_TYPE["unknown"])
    if ideal_min <= duration <= ideal_max:
        duration_score = 0.20
    elif duration < ideal_min:
        # Shorter than ideal — penalise proportionally
        duration_score = 0.20 * (duration / ideal_min)
    else:
        # Too long — soft penalty
        overshoot = (duration - ideal_max) / ideal_max
        duration_score = max(0.04, 0.20 * (1 - min(overshoot, 1)))

    # Opening hook: first 6 words
    first_words = " ".join(words[:6])
    hook_score = 0.0
    for k, w in _KEYWORD_WEIGHTS.items():
        if k in first_words:
            hook_score = max(hook_score, min(0.20, w))

    # Speech rate bonus (fix #11) — reward 2.0–3.5 WPS (energetic but clear)
    wps = len(words) / duration if duration > 0 else 0
    if 2.0 <= wps <= 3.5:
        speech_rate_score = 0.08
    elif 1.5 <= wps < 2.0 or 3.5 < wps <= 4.5:
        speech_rate_score = 0.04
    else:
        speech_rate_score = 0.0

    combined = min(1.0, keyword_score + emo_score + duration_score + hook_score + speech_rate_score)

    return {
        "keyword_score":     round(keyword_score, 3),
        "emotion_score":     round(emo_score, 3),
        "duration_score":    round(duration_score, 3),
        "hook_score":        round(hook_score, 3),
        "speech_rate_score": round(speech_rate_score, 3),
        "words_per_sec":     round(wps, 2),
        "combined":          round(combined, 3),
    }


def _heatmap_overlap_score(start: float, end: float, heatmap_segments: list) -> float:
    if not heatmap_segments:
        return 0.0
    overlap_score = 0.0
    for hm in heatmap_segments:
        hm_start = float(hm.get("start", 0))
        hm_end = hm_start + float(hm.get("duration", 0))
        hm_score = float(hm.get("score", 0))
        overlap = max(0, min(end, hm_end) - max(start, hm_start))
        overlap_ratio = overlap / (end - start) if end > start else 0
        overlap_score = max(overlap_score, overlap_ratio * hm_score)
    return round(overlap_score, 3)


# ---------------------------------------------------------------------------
# SEGMENT MERGING WITH COHERENCE GUARD  (fix #6)
# ---------------------------------------------------------------------------

def _word_overlap_ratio(text_a: str, text_b: str) -> float:
    """Rough lexical overlap — prevents merging totally unrelated sentences."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    # Remove very common stop words that always overlap
    stops = {"the", "a", "an", "is", "are", "was", "and", "or", "i", "it", "to", "of", "in", "that", "this", "you"}
    words_a -= stops
    words_b -= stops
    if not words_a or not words_b:
        return 1.0   # too short to judge — allow merge
    union = words_a | words_b
    intersection = words_a & words_b
    return len(intersection) / len(union)


def _merge_segments(transcript_segments: list) -> list[ClipCandidate]:
    """
    Merge adjacent transcript segments into clip-length candidates.
    Segments are only merged if they are temporally close AND lexically coherent.
    """
    candidates: list[ClipCandidate] = []

    def flush(indices, texts, start, end):
        if not texts:
            return
        text = " ".join(texts).strip()
        if len(text) < 10:
            return
        candidates.append(
            ClipCandidate(
                segment_indices=indices,
                start_time=start,
                end_time=end,
                duration=end - start,
                text=text,
            )
        )

    current_start = None
    current_end = None
    current_texts: list[str] = []
    current_indices: list[int] = []

    for i, seg in enumerate(transcript_segments):
        seg_start = float(seg.get("start", 0))
        seg_dur   = float(seg.get("duration", 0))
        seg_end   = seg_start + seg_dur
        seg_text  = seg.get("text", "").strip()

        if current_start is None:
            current_start = seg_start
            current_end   = seg_end
            current_indices = [i]
            current_texts   = [seg_text]
            continue

        gap     = seg_start - current_end
        new_dur = seg_end - current_start

        # Time proximity check
        time_ok = gap <= MERGE_GAP_SEC and new_dur <= IDEAL_CLIP_MAX_SEC

        # Coherence check: don't merge if the new sentence is totally unrelated (fix #6)
        current_text_so_far = " ".join(current_texts)
        coherent = _word_overlap_ratio(current_text_so_far[-200:], seg_text) >= 0.05

        if time_ok and coherent:
            current_end = seg_end
            current_indices.append(i)
            current_texts.append(seg_text)
        else:
            flush(current_indices, current_texts, current_start, current_end)
            current_start = seg_start
            current_end   = seg_end
            current_indices = [i]
            current_texts   = [seg_text]

    flush(current_indices, current_texts, current_start, current_end)
    return candidates


# ---------------------------------------------------------------------------
# AI SCORING  (fix #7 — enriched prompt with video metadata)
# ---------------------------------------------------------------------------
_AI_SYSTEM_PROMPT = """You are an elite short-form video strategist who has grown multiple creator accounts past 1M followers by identifying and clipping viral moments from long-form podcasts.

Your singular mission: find moments that will stop the scroll in 3 seconds, sustain attention until the final frame, and make viewers feel compelled to share.

## WHAT MAKES A GREAT CLIP

**Hook Quality (most critical)**
- Opens mid-action, mid-conflict, or mid-revelation — never with greetings or scene-setting
- First line triggers an open loop: curiosity, tension, or disbelief ("I almost lost everything", "Nobody talks about this", "That's when I realized I was wrong")
- The viewer's instant reaction must be: *"Wait — what happens next?"*

**Narrative Arc**
- Follows a tight structure: hook → tension/build → payoff, all within 30–90 seconds
- Completely self-contained: a cold viewer with zero context must understand AND enjoy it
- Lands on a satisfying close — a punchline, a revelation, a mic-drop statement, or an emotional peak
- Never ends mid-thought or before the resolution

**Viral Signals — prioritize moments that are:**
- Counterintuitive or myth-busting ("Everyone believes X — here's why they're wrong")
- Emotionally raw: genuine vulnerability, unscripted laughter, real disagreement, visible discomfort
- Universally relatable — taps shared human experiences, not niche in-jokes
- Quotable — contains one line people would screenshot or put on a caption
- Debate-worthy — triggers strong enough opinions to generate comment wars (without being harmful)
- Surprising — the viewer's expectation is subverted at the payoff

**Hard Disqualifiers — never select clips that:**
- Open with "So today we're talking about...", "Welcome back", or any greeting
- Require external context to make sense (references unexplained people, events, or prior conversation)
- Build slowly with no emotional peak or payoff
- Resolve in under 15 seconds (no tension) or stretch past 90 seconds without escalation
- End on a trailing thought, interruption, or an unresolved question

## YOUR MENTAL MODEL
Before scoring any clip, ask:
1. If I watched this with zero context at 2am, would I stop scrolling?
2. Would I send this to a friend?
3. Is there one line I'd remember tomorrow?

If the answer to all three is no — reject the clip."""


# ─── STAGE 1: CANDIDATE DISCOVERY ─────────────────────────────────────────────
# Feed full transcript → AI returns timestamp candidates
_AI_DISCOVERY_TEMPLATE = """\
You are scanning a full podcast/video transcript to DISCOVER the best clip candidates.
Do NOT score them yet. Your only job is to find moments worth evaluating.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIDEO CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title:         {video_title}
Description:   {video_description}
Content type:  {content_type}
Editing style: {editing_style}
Language:      {language}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FULL TRANSCRIPT (with timestamps)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{full_transcript}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Read the ENTIRE transcript. Then identify {max_candidates} clip candidates (target: 20–60 seconds each).

DISCOVERY SIGNALS — hunt for moments where:
- A speaker says something surprising, counterintuitive, or emotionally charged
- An argument, disagreement, or tension peaks
- A personal story reaches its climax or turning point
- A single quotable sentence lands that could stand alone
- The energy or pacing of the conversation visibly shifts
- A confession, reveal, or vulnerability moment occurs
- Someone says "the truth is...", "nobody talks about...", "I never told anyone...", "that's when I realized..."

BOUNDARY RULES:
- Start BEFORE the hook line (2-3s before the key sentence, at a natural speech boundary)
- End AFTER the payoff has fully landed (include the reaction/pause if present)
- Minimum: 15 seconds. Maximum: 90 seconds.
- Never start mid-sentence. Never end mid-thought.

Return ONLY a valid JSON array — no markdown, no explanation:

[
  {{
    "candidate_index": <int, 1-based>,
    "start":           <float, seconds>,
    "end":             <float, seconds>,
    "hook_line":       "<the exact opening line of this candidate — max 15 words>",
    "signal_type":     "<what viral signal triggered this pick: reveal | conflict | story_peak | quotable | emotional | counterintuitive | confession>",
    "why_interesting": "<one sentence on why this moment is worth scoring — max 30 words>"
  }},
  ...
]

Sort by estimated interest level, highest first.
{custom_instructions}"""


_AI_USER_TEMPLATE = """\
Analyze the following clip candidates from a long-form video/podcast.
Find clips with the highest standalone viral potential for short-form portrait video (9:16).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIDEO CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title:         {video_title}
Description:   {video_description}
Channel size:  {channel_size_tier}     (small <10K | medium 10K–500K | large >500K)
Content type:  {content_type}          (e.g. comedy, educational, commentary, story, interview)
Editing style: {editing_style}         (e.g. talking-head, heavily-edited, b-roll-heavy, podcast)
Captions:      {captions_available}    (yes/no — directly impacts standalone_score ceiling)
Language:      English                 (e.g. English, Thai, bilingual — affects hook phrasing)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FULL TRANSCRIPT (condensed — for full narrative context only, do not clip from this directly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{full_transcript}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLIP CANDIDATES (evaluate only these segments)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{clips_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORING DIMENSIONS (0.0–1.0 each)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. hook_score        — Does the opening line create an open loop within 3 seconds?
                       1.0 = starts mid-revelation or mid-conflict, impossible to look away
                       0.0 = opens with greeting, filler, or slow build

2. standalone_score  — Can a cold viewer with ZERO prior context understand and enjoy this?
                       1.0 = fully self-explanatory, no unexplained references
                       0.0 = requires knowledge of prior conversation, people, or events
                       ⚠ Auto-cap at 0.6 if captions are unavailable

3. emotion_score     — Triggers a strong, specific feeling (surprise, humor, awe, outrage, inspiration, discomfort)?
                       1.0 = visceral, unmistakable emotional peak
                       0.0 = flat, informational, no emotional charge

4. arc_score         — Does the clip have a complete narrative arc: hook → tension → payoff?
                       1.0 = clear beginning, escalation, and satisfying close
                       0.0 = starts or ends abruptly, or lacks internal resolution

5. replay_score      — Is there a moment worth rewatching (a reveal, a punchline, a visual peak)?
                       1.0 = contains a single moment that rewards a second watch
                       0.0 = linear, no rewatch value

6. trend_score       — Taps into a universal relatable experience, cultural debate, or evergreen topic?
                       1.0 = deeply relatable or culturally resonant right now
                       0.0 = highly niche, insider, or time-locked

WEIGHTED VIRAL SCORE:
  viral_score = hook(0.25) + standalone(0.20) + emotion(0.20) + arc(0.15) + replay(0.10) + trend(0.10)

CHANNEL SIZE WEIGHT ADJUSTMENTS:
  small  (<10K):   standalone_score weight ×1.3 — unknown creator, cold viewers need full context
  medium (10K–500K): use weights as-is
  large  (>500K):  hook_score weight ×1.3 — algorithm-driven cold traffic dominates

PLATFORM FIT HEURISTICS:
  tiktok:  ≤60s, fast-paced, humor or trending angle, punchy hook in first 2s
  reels:   ≤90s, aesthetic or inspirational, slightly slower burn acceptable
  shorts:  ≤60s, high hook density, YouTube-native audience responds to educational/story arcs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON array — no markdown fences, no preamble, no explanation outside the JSON.

[
  {{
    "clip_index":          <int, 1-based within this batch>,
    "viral_score":         <float 0.0–1.0>,
    "hook_score":          <float>,
    "standalone_score":    <float>,
    "emotion_score":       <float>,
    "arc_score":           <float>,
    "replay_score":        <float>,
    "trend_score":         <float>,
    "suggested_start":     <float, adjusted start in seconds — keep original if already optimal>,
    "suggested_end":       <float, adjusted end in seconds — keep original if already optimal>,
    "hook_preview":        "<exact opening line that hooks the viewer — max 15 words>",
    "payoff_preview":      "<the closing line or moment that delivers the resolution — max 15 words>",
    "clip_reason":         "<why this works standalone and why it would go viral — max 50 words>",
    "suggested_clip_title":"<scroll-stopping title for the short — max 10 words>",
    "platform_fit":        ["tiktok", "reels", "shorts"],
    "trim_notes":          "<optional: specific cut or pacing note for the editor — max 20 words, or null>"
  }},
  ...
]

Only include clips with viral_score >= {min_score}. Sort by viral_score descending.
{custom_instructions}"""


def _build_clips_text(candidates: list[ClipCandidate]) -> str:
    lines = []
    for i, c in enumerate(candidates, 1):
        wps = c.dimension_scores.get("words_per_sec", 0)
        lines.append(
            f"[{i}] {_fmt_time(c.start_time)}–{_fmt_time(c.end_time)} "
            f"({c.duration:.0f}s) | type={c.content_type} | "
            f"heuristic={c.heuristic_score:.2f} | heatmap={c.heatmap_score:.2f} | "
            f"wps={wps:.1f}\n"
            f"    TEXT: {c.text[:800]}{'...' if len(c.text) > 800 else ''}"
        )
    return "\n\n".join(lines)


def _build_full_transcript_context(transcript_segments: list[dict]) -> str:
    """Build the complete transcript for AI context.
    
    Groups transcript into time-chunked paragraphs so the AI can understand
    the full narrative flow of the video, not just isolated fragments.
    No truncation — the AI receives the entire transcript for maximum context.
    """
    if not transcript_segments:
        return "(no transcript available)"
    
    lines = []
    chunk_texts = []
    chunk_start = 0.0
    chunk_end = 0.0
    
    for seg in transcript_segments:
        seg_start = float(seg.get("start", 0))
        seg_dur = float(seg.get("duration", 0))
        seg_end = seg_start + seg_dur
        seg_text = seg.get("text", "").strip()
        if not seg_text:
            continue
        
        if not chunk_texts:
            chunk_start = seg_start
        
        chunk_texts.append(seg_text)
        chunk_end = seg_end
        
        # Flush every ~30 seconds of content
        if chunk_end - chunk_start >= 30 or seg == transcript_segments[-1]:
            paragraph = " ".join(chunk_texts)
            lines.append(f"[{_fmt_time(chunk_start)}–{_fmt_time(chunk_end)}] {paragraph}")
            chunk_texts = []
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# STAGE 1: AI DISCOVERY — find interesting moments from full transcript
# ---------------------------------------------------------------------------

def _call_ai_discovery(
    transcript_segments: list[dict],
    video_title: str,
    video_description: str,
    custom_prompt: str = "",
    content_type: str = "unknown",
    editing_style: str = "unknown",
    language: str = "English",
    max_candidates: int = 15,
) -> list[dict]:
    """
    Stage 1: Send the full transcript to AI and ask it to discover
    the most interesting moments. Returns a list of candidate dicts
    with 'start', 'end', 'hook_line', 'signal_type', 'why_interesting'.
    """
    full_transcript = _build_full_transcript_context(transcript_segments)

    prompt = _AI_DISCOVERY_TEMPLATE.format(
        video_title=video_title or "(untitled)",
        video_description=(video_description or "")[:500],
        content_type=content_type,
        editing_style=editing_style,
        language=language,
        full_transcript=full_transcript,
        max_candidates=max_candidates,
        custom_instructions=(f"\nCustom instructions:\n{custom_prompt}" if custom_prompt else ""),
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.AI_API_KEY}",
    }
    payload = {
        "model": config.discover_ai_model(),
        "messages": [
            {"role": "system", "content": _AI_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.5,
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                config.get_ai_chat_url(), headers=headers, json=payload, timeout=120
            )
            resp.raise_for_status()
            resp_json = resp.json()
            choices = resp_json.get("choices", [])
            if not choices:
                raise ValueError(f"AI returned no choices: {list(resp_json.keys())}")
            raw = choices[0].get("message", {}).get("content", "")
            if not raw:
                raise ValueError("AI returned empty content")

            parsed, was_repaired = _safe_json(raw)
            if was_repaired:
                print("  [discovery] JSON was repaired (truncated response)")

            if parsed is None:
                raise ValueError(f"Could not parse JSON from AI response (len={len(raw)})")
            if isinstance(parsed, dict):
                parsed = [parsed]
            if not isinstance(parsed, list):
                raise ValueError(f"AI returned unexpected type: {type(parsed).__name__}")

            # Validate and clean candidates
            valid = []
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                try:
                    s = float(item.get("start", 0))
                    e = float(item.get("end", 0))
                    if e > s and (e - s) >= IDEAL_CLIP_MIN_SEC:
                        valid.append({
                            "start": s,
                            "end": e,
                            "duration": e - s,
                            "hook_line": item.get("hook_line", ""),
                            "signal_type": item.get("signal_type", ""),
                            "why_interesting": item.get("why_interesting", ""),
                        })
                except (TypeError, ValueError):
                    continue

            print(f"  [discovery] AI found {len(valid)} candidate moments")
            return valid

        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
            print(f"  [discovery] attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    return []


# ---------------------------------------------------------------------------
# STAGE 2: AI SCORING  (score & rank candidates from discovery)
# ---------------------------------------------------------------------------

def _call_ai(
    candidates: list[ClipCandidate],
    video_title: str,
    video_description: str,
    custom_prompt: str,
    channel_size_tier: str = "unknown",
    content_type: str = "unknown",
    editing_style: str = "unknown",
    captions_available: bool = True,
    full_transcript_context: str = "",
) -> dict[int, dict]:
    """
    Stage 2: Send candidates to AI for scoring and ranking.
    Returns dict: {candidate_index_0based: ai_result_dict}
    """
    results: dict[int, dict] = {}
    batches = [
        candidates[i:i + MAX_SEGMENTS_PER_BATCH]
        for i in range(0, len(candidates), MAX_SEGMENTS_PER_BATCH)
    ]

    for batch_offset, batch in enumerate(batches):
        clips_text = _build_clips_text(batch)

        # Dominant content type across this batch
        batch_content_type = (
            max(set(c.content_type for c in batch), key=lambda t: sum(1 for c in batch if c.content_type == t))
            if batch else content_type
        )

        prompt = _AI_USER_TEMPLATE.format(
            video_title=video_title or "(untitled)",
            video_description=(video_description or "")[:500],
            channel_size_tier=channel_size_tier,
            content_type=batch_content_type,
            editing_style=editing_style,
            captions_available="yes" if captions_available else "no",
            full_transcript=full_transcript_context or "(not available)",
            clips_text=clips_text,
            min_score=MIN_VIRAL_SCORE,
            custom_instructions=(f"\nCustom instructions:\n{custom_prompt}" if custom_prompt else ""),
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.AI_API_KEY}",
        }
        payload = {
            "model": config.discover_ai_model(),
            "messages": [
                {"role": "system", "content": _AI_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.4,
        }

        for attempt in range(3):
            try:
                resp = requests.post(
                    config.get_ai_chat_url(), headers=headers, json=payload, timeout=120
                )
                resp.raise_for_status()
                resp_json = resp.json()
                choices = resp_json.get("choices", [])
                if not choices:
                    raise ValueError(f"AI returned no choices: {list(resp_json.keys())}")
                raw = choices[0].get("message", {}).get("content", "")
                if not raw:
                    raise ValueError("AI returned empty content")

                parsed, was_repaired = _safe_json(raw)   # fix #10
                if was_repaired:
                    print(f"  [ai] batch {batch_offset + 1}: JSON was repaired (truncated response)")

                if parsed is None:
                    raise ValueError(f"Could not parse JSON from AI response (len={len(raw)})")
                if isinstance(parsed, dict):
                    parsed = [parsed]
                if not isinstance(parsed, list):
                    raise ValueError(f"AI returned unexpected type: {type(parsed).__name__}")

                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    local_idx  = item.get("clip_index", 0) - 1
                    global_idx = batch_offset * MAX_SEGMENTS_PER_BATCH + local_idx
                    results[global_idx] = item
                break

            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
                print(f"  [ai] batch {batch_offset + 1}, attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)

    return results


# ---------------------------------------------------------------------------
# SCORE FUSION  (fix #2 — uses adaptive weights)
# ---------------------------------------------------------------------------

def _fuse_scores(
    heuristic: float,
    heatmap: float,
    ai: float,
    has_ai: bool,
    weights: dict,
) -> float:
    if has_ai:
        return round(
            ai        * weights["ai"] +
            heatmap   * weights["heatmap"] +
            heuristic * weights["heuristic"],
            4,
        )
    else:
        return round(
            heatmap   * weights["heatmap_fallback"] +
            heuristic * weights["heuristic_fallback"],
            4,
        )


# ---------------------------------------------------------------------------
# NMS DEDUPLICATION  (fix #9)
# ---------------------------------------------------------------------------

def _time_overlap_ratio(a: ClipCandidate, b: ClipCandidate) -> float:
    """Fraction of the shorter clip's duration that overlaps with the other."""
    overlap = max(0, min(a.end_time, b.end_time) - max(a.start_time, b.start_time))
    shorter_dur = min(a.duration, b.duration)
    return overlap / shorter_dur if shorter_dur > 0 else 0.0


def _nms_filter(candidates: list[ClipCandidate], overlap_threshold: float = NMS_OVERLAP_THRESHOLD) -> list[ClipCandidate]:
    """
    Non-maximum suppression: if a lower-scored clip overlaps a higher-scored clip
    by more than overlap_threshold, suppress the lower-scored one.
    Candidates must be pre-sorted by score descending.
    """
    kept: list[ClipCandidate] = []
    for candidate in candidates:
        suppressed = any(
            _time_overlap_ratio(candidate, k) > overlap_threshold
            for k in kept
        )
        if not suppressed:
            kept.append(candidate)
    return kept


# ---------------------------------------------------------------------------
# PRE-FILTER  (fix #4 — ratio-based)
# ---------------------------------------------------------------------------

def _compute_top_n(total: int) -> int:
    n = max(PRE_FILTER_MIN, int(total * PRE_FILTER_RATIO))
    return min(n, PRE_FILTER_MAX)


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def analyze_transcript_with_ai(
    transcript_segments: list[dict],
    video_title: str = "",
    video_description: str = "",
    custom_prompt: str = "",
    heatmap_segments: list | None = None,
    # New metadata params (fix #7)
    channel_size_tier: str = "unknown",   # "small" | "medium" | "large" | "unknown"
    editing_style: str = "unknown",       # "talking-head" | "heavily-edited" | "b-roll-heavy" | "podcast"
    captions_available: bool = True,
) -> list[dict]:
    """
    Full pipeline: heuristic → heatmap → (AI) → fuse → NMS → rank → return clips.

    Args:
        transcript_segments:  Raw transcript dicts with 'start', 'duration', 'text'.
        video_title:          Video title for AI context.
        video_description:    Video description (truncated to 500 chars).
        custom_prompt:        Extra instructions appended to the AI prompt.
        heatmap_segments:     YouTube heatmap segments with 'start', 'duration', 'score'.
        channel_size_tier:    Channel size bucket — influences AI scoring emphasis.
        editing_style:        Rough description of how the video is edited.
        captions_available:   Whether captions will be burned in (affects standalone score).

    Returns:
        List of clip dicts sorted by final_score descending.
    """
    heatmap_segments = heatmap_segments or []
    custom_prompt    = (custom_prompt or getattr(config, "AI_SEGMENT_PROMPT", "") or "").strip()

    # ── 1. Load adaptive weights ────────────────────────────────────────────
    weights = _load_fusion_weights()

    # ── 2. Merge raw segments into clip candidates ──────────────────────────
    candidates = _merge_segments(transcript_segments)
    if not candidates:
        return []

    # ── 3. Detect content type per candidate ───────────────────────────────
    for c in candidates:
        c.content_type = _detect_content_type(c.text)

    # ── 4. Heuristic score ─────────────────────────────────────────────────
    for c in candidates:
        dims = _heuristic_score(c.text, c.duration, c.content_type)
        c.dimension_scores.update(dims)
        c.heuristic_score = dims["combined"]

    # ── 5. Heatmap score ───────────────────────────────────────────────────
    for c in candidates:
        c.heatmap_score = _heatmap_overlap_score(c.start_time, c.end_time, heatmap_segments)

    # ── 6. Determine Candidates (AI Discovery vs Heuristic Pre-filter) ─────
    top_candidates = []
    rest_candidates = []
    ai_results: dict[int, dict] = {}
    
    # Dominant content type across full video (for AI prompt)
    all_types = [c.content_type for c in candidates]
    dominant_type = max(set(all_types), key=all_types.count) if all_types else "unknown"

    if getattr(config, "AI_API_KEY", None):
        print(f"[pipeline] Starting TWO-STAGE AI Pipeline...")
        # STAGE 1: Discovery from full transcript
        try:
            discovery_results = _call_ai_discovery(
                transcript_segments=transcript_segments,
                video_title=video_title,
                video_description=video_description,
                custom_prompt=custom_prompt,
                content_type=dominant_type,
                editing_style=editing_style,
            )
            
            # Convert discovered timestamps into ClipCandidates
            for idx, dr in enumerate(discovery_results):
                # Build a text block for this candidate from original transcript
                c_start, c_end = dr["start"], dr["end"]
                c_text_parts = []
                for seg in transcript_segments:
                    s_start = float(seg.get("start", 0))
                    s_dur = float(seg.get("duration", 0))
                    s_end = s_start + s_dur
                    if s_end > c_start and s_start < c_end:
                        c_text_parts.append(seg.get("text", ""))
                
                c_text = " ".join(c_text_parts)
                c_dur = c_end - c_start
                c_type = _detect_content_type(c_text)
                
                # Create a fresh candidate matching the AI's discovered segment
                cand = ClipCandidate(
                    segment_indices=[],
                    start_time=c_start,
                    end_time=c_end,
                    duration=c_dur,
                    text=c_text,
                    content_type=c_type,
                )
                dims = _heuristic_score(cand.text, cand.duration, cand.content_type)
                cand.dimension_scores.update(dims)
                cand.heuristic_score = dims["combined"]
                cand.heatmap_score = _heatmap_overlap_score(cand.start_time, cand.end_time, heatmap_segments)
                top_candidates.append(cand)
            
            print(f"[pipeline] Stage 1 finished. {len(top_candidates)} candidates created from discovery.")
            
        except Exception as e:
            print(f"[pipeline] Stage 1 (Discovery) failed: {e}")
            top_candidates = [] # fallback to heuristic
            
        # STAGE 2: Scoring
        if top_candidates:
            full_transcript_ctx = _build_full_transcript_context(transcript_segments)
            try:
                ai_results = _call_ai(
                    top_candidates,
                    video_title,
                    video_description,
                    custom_prompt,
                    channel_size_tier=channel_size_tier,
                    content_type=dominant_type,
                    editing_style=editing_style,
                    captions_available=captions_available,
                    full_transcript_context=full_transcript_ctx,
                )
            except Exception as e:
                print(f"[pipeline] Stage 2 (Scoring) skipped: {e}")
                
    # Fallback if AI disabled or Stage 1 failed (old heuristic approach)
    if not top_candidates:
        pre_scored = sorted(
            candidates,
            key=lambda c: _fuse_scores(c.heuristic_score, c.heatmap_score, 0, False, weights),
            reverse=True,
        )
        n_top = _compute_top_n(len(pre_scored))
        top_candidates  = pre_scored[:n_top]
        rest_candidates = pre_scored[n_top:]
        print(f"[pipeline] Fallback to heuristic pre-filter. {len(candidates)} candidates → top {n_top} selected.")

    # ── 7. Apply AI results & fuse final scores ────────────────────────────
    for i, c in enumerate(top_candidates):
        ai_data = ai_results.get(i, {})
        has_ai  = bool(ai_data)

        c.ai_score    = float(ai_data.get("viral_score", 0.0))
        c.final_score = _fuse_scores(c.heuristic_score, c.heatmap_score, c.ai_score, has_ai, weights)

        c.hook_preview       = ai_data.get("hook_preview", "")
        c.clip_reason        = ai_data.get("clip_reason", "")
        c.suggested_clip_title = ai_data.get("suggested_clip_title", "")
        c.platform_fit       = ai_data.get("platform_fit", [])

        # Apply AI-suggested boundary adjustments (trimming notes)
        suggested_start = ai_data.get("suggested_start")
        suggested_end   = ai_data.get("suggested_end")
        if suggested_start is not None and suggested_end is not None:
            try:
                s_start = float(suggested_start)
                s_end   = float(suggested_end)
                s_dur   = s_end - s_start
                # Sanity: non-negative start, end after start, minimum duration
                if s_start >= 0 and s_dur >= IDEAL_CLIP_MIN_SEC:
                    if s_start != c.start_time or s_end != c.end_time:
                        print(f"  [ai] Clip {i+1}: adjusted boundaries "
                              f"{_fmt_time(c.start_time)}–{_fmt_time(c.end_time)} → "
                              f"{_fmt_time(s_start)}–{_fmt_time(s_end)}")
                    c.start_time = s_start
                    c.end_time   = s_end
                    c.duration   = s_dur
            except (TypeError, ValueError):
                pass

        c.dimension_scores.update({
            "hook":       ai_data.get("hook_score", 0.0),
            "standalone": ai_data.get("standalone_score", 0.0),
            "emotion":    ai_data.get("emotion_score", 0.0),
            "replay":     ai_data.get("replay_score", 0.0),
            "trend":      ai_data.get("trend_score", 0.0),
            "arc":        ai_data.get("arc_score", 0.0),  # updated field name
            "combined":   c.final_score,
        })

    # ── 8. Heuristic-only candidates ───────────────────────────────────────
    for c in rest_candidates:
        c.final_score = _fuse_scores(c.heuristic_score, c.heatmap_score, 0, False, weights)

    # ── 9. Filter by minimum score ─────────────────────────────────────────
    all_candidates = [c for c in (top_candidates + rest_candidates) if c.final_score >= MIN_VIRAL_SCORE]

    # ── 10. Sort then NMS deduplication (fix #9) ───────────────────────────
    all_candidates.sort(key=lambda c: c.final_score, reverse=True)
    all_candidates = _nms_filter(all_candidates)

    return [
        {
            "start":                 c.start_time,
            "end":                   c.end_time,
            "duration":              c.duration,
            "text":                  c.text,
            "content_type":          c.content_type,
            "score":                 c.final_score,
            "dimension_scores":      c.dimension_scores,
            "hook_preview":          c.hook_preview,
            "clip_reason":           c.clip_reason,
            "suggested_clip_title":  c.suggested_clip_title,
            "platform_fit":          c.platform_fit,
        }
        for c in all_candidates
    ]