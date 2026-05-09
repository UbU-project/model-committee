import json
import re
from typing import Any

from model_committee.errors import ModelOutputError

FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)
THINK_RE = re.compile(r"<think\b[^>]*>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
THINK_TAG_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)


def strip_thinking_blocks(text: str) -> str:
    return THINK_RE.sub("", text)


def _embedded_json_objects(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for match in re.finditer(r"\{", text):
        try:
            parsed, _end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
    return objects


def extract_json_object(text: str) -> dict[str, Any]:
    has_thinking_tag = THINK_TAG_RE.search(text) is not None
    stripped = strip_thinking_blocks(text).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    fences = FENCE_RE.findall(stripped)
    if len(fences) != 1:
        if has_thinking_tag:
            embedded = _embedded_json_objects(stripped)
            if len(embedded) == 1:
                return embedded[0]
        raise ModelOutputError("expected exactly one JSON object or fenced JSON block")
    try:
        fenced = json.loads(fences[0].strip())
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"fenced block is not valid JSON: {exc}") from exc
    if not isinstance(fenced, dict):
        raise ModelOutputError("JSON output must be an object")
    return fenced
