import os


def summarize_transcript_segments(segments, limit=10, include_text=True):
    lines = []
    for i, seg in enumerate(segments[:limit], start=1):
        start = float(seg.get("start", 0))
        duration = float(seg.get("duration", 0))
        end = start + duration
        text = seg.get("text", "").strip()
        if include_text and text:
            if len(text) > 280:
                text = text[:277] + "..."
            lines.append(f"Segment {i} ({start:.1f}s-{end:.1f}s): {text}")
        else:
            lines.append(f"Segment {i} ({start:.1f}s-{end:.1f}s)")
    return "\n".join(lines)


def summarize_heatmap_segments(segments, limit=10):
    lines = []
    for i, seg in enumerate(segments[:limit], start=1):
        start = float(seg.get("start", 0))
        duration = float(seg.get("duration", 0))
        end = start + duration
        score = float(seg.get("score", 0))
        lines.append(f"Heatmap {i} ({start:.1f}s-{end:.1f}s) score {score:.2f}")
    return "\n".join(lines)