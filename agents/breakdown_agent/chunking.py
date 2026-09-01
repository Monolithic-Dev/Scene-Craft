"""Splits a script on scene-heading boundaries rather than a fixed token
count — a scene should never be split mid-scene across two chunks, since
that produces duplicate/contradictory shot numbers with no shared context
between the two halves. See PHASE-02-BREAKDOWN-AGENT.md Common Pitfalls #1.
"""
import re

# Standard screenplay slugline: INT./EXT./INT./EXT. (or I/E.) at line start.
_SCENE_HEADING_RE = re.compile(r"^\s*(INT|EXT|INT\.?/EXT|I/E)[\./ ]", re.IGNORECASE | re.MULTILINE)

# A single Gemini call comfortably handles a scene this long; only scenes
# pathologically longer than this get sub-split (rare — most real scenes are
# well under this).
_MAX_CHUNK_CHARS = 12_000


def chunk_script(script_text: str) -> list[str]:
    """Returns one chunk per scene, in order. A script with no recognizable
    scene headings at all becomes a single chunk — better to hand the whole
    thing to the model than to silently produce zero chunks.
    """
    heading_starts = [m.start() for m in _SCENE_HEADING_RE.finditer(script_text)]
    if not heading_starts:
        return [script_text] if script_text.strip() else []

    boundaries = [*heading_starts, len(script_text)]
    scenes = [
        script_text[start:end].strip()
        for start, end in zip(boundaries, boundaries[1:], strict=False)
    ]
    scenes = [scene for scene in scenes if scene]

    chunks: list[str] = []
    for scene in scenes:
        chunks.extend(_split_if_too_long(scene))
    return chunks


def _split_if_too_long(scene_text: str) -> list[str]:
    if len(scene_text) <= _MAX_CHUNK_CHARS:
        return [scene_text]

    # Pathologically long scene: fall back to paragraph-boundary splitting
    # rather than an arbitrary character cut mid-sentence.
    paragraphs = scene_text.split("\n\n")
    sub_chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > _MAX_CHUNK_CHARS and current:
            sub_chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        sub_chunks.append(current)
    return sub_chunks
