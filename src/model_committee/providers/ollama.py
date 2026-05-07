import re
from pathlib import Path

import httpx

from model_committee.config import OllamaConfig, OllamaModelConfig
from model_committee.errors import ProviderError
from model_committee.responses.json_extract import extract_json_object
from model_committee.responses.schemas import WorkProposal


def safe_model_name(name: str) -> str:
    value = name.lower().replace("/", "__").replace(":", "--").replace(" ", "_")
    return re.sub(r"[^a-z0-9_.-]", "", value)


class OllamaWorkProvider:
    def __init__(self, ollama_config: OllamaConfig, model_config: OllamaModelConfig):
        self.ollama_config = ollama_config
        self.model_config = model_config
        self.safe_name = safe_model_name(model_config.name)
        self.provider_id = f"ollama:{self.safe_name}"

    def generate_work_proposal(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> WorkProposal:
        del schema_path
        response_path = run_dir / "responses" / f"ollama_{self.safe_name}_response.txt"
        body = {
            "model": self.model_config.name,
            "prompt": prompt_path.read_text(encoding="utf-8"),
            "stream": False,
            "options": {
                "temperature": self.model_config.temperature,
                "top_p": self.model_config.top_p,
                "repeat_penalty": self.model_config.repeat_penalty,
                "num_predict": self.model_config.num_predict,
                "num_ctx": self.model_config.max_context_tokens,
            },
        }
        url = self.ollama_config.base_url.rstrip("/") + "/api/generate"
        try:
            with httpx.Client(timeout=self.model_config.timeout_seconds) as client:
                result = client.post(url, json=body)
                result.raise_for_status()
        except httpx.HTTPError as exc:
            message = f"ollama request failed for {self.model_config.name}: {exc}"
            raise ProviderError(message) from exc
        text = result.json().get("response", "")
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(text, encoding="utf-8")
        return WorkProposal.model_validate(extract_json_object(text))


def check_ollama_reachable(base_url: str) -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=3) as client:
            result = client.get(base_url.rstrip("/") + "/api/tags")
            result.raise_for_status()
        return True, "reachable"
    except httpx.HTTPError as exc:
        return False, str(exc)


def list_ollama_models(base_url: str) -> list[str]:
    with httpx.Client(timeout=3) as client:
        result = client.get(base_url.rstrip("/") + "/api/tags")
        result.raise_for_status()
    data = result.json()
    return [model.get("name", "") for model in data.get("models", []) if model.get("name")]
