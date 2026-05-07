import json
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from model_committee.constants import DEFAULT_CONFIG_PATH
from model_committee.errors import ConfigError


class CodexConfig(BaseModel):
    enabled: bool = True
    command: str = "codex"
    model: str = "gpt-5.5"
    timeout_seconds: int = 3600
    weight: float = 1.0
    sandbox: str = "read-only"
    use_json_events: bool = True
    working_directory: str = "../ubu-design"
    prompt_input_mode: str = "stdin"


class OllamaModelConfig(BaseModel):
    name: str
    enabled: bool = True
    priority: int = 1
    weight: float = 0.35
    max_context_tokens: int = 32768
    timeout_seconds: int = 1800
    temperature: float = 0.2
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    num_predict: int = 4096
    notes: str = ""


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    models: list[OllamaModelConfig] = Field(default_factory=list)

    @field_validator("base_url")
    @classmethod
    def validate_local_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Ollama base_url must use http or https")
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Ollama base_url must point to localhost")
        return value


class ModelCommitteeConfig(BaseModel):
    codex: CodexConfig = Field(default_factory=CodexConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)


def load_config(path: Path | None) -> ModelCommitteeConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return ModelCommitteeConfig()
    try:
        return ModelCommitteeConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ConfigError(f"invalid config {config_path}: {exc}") from exc
