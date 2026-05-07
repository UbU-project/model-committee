import json
import re
from typing import Any

from model_committee.errors import ModelOutputError

FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    fences = FENCE_RE.findall(stripped)
    if len(fences) != 1:
        raise ModelOutputError("expected exactly one JSON object or fenced JSON block")
    try:
        fenced = json.loads(fences[0].strip())
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"fenced block is not valid JSON: {exc}") from exc
    if not isinstance(fenced, dict):
        raise ModelOutputError("JSON output must be an object")
    return fenced
