import pytest

from model_committee.config import ModelCommitteeConfig
from model_committee.config import OllamaConfig, OllamaModelConfig
from model_committee.providers.ollama import OllamaWorkProvider


def test_ollama_provider_uses_configured_base_url(monkeypatch, tmp_path):
    seen = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": '{"proposal_id":"x","provider_id":"ollama:m","model_name":"m",'
                '"question_id":"UBU-Q0001","base_commit":"unknown","summary":"s",'
                '"rationale":"r","changed_files":["DESIGN.md"],'
                '"patch":"diff --git a/DESIGN.md b/DESIGN.md\\n",'
                '"commit_message":"c","validation_notes":[],"new_questions_added":[],'
                '"questions_resolved":[],"decisions_added":[],"requires_human_review":false}'
            }

    class Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json):
            seen["url"] = url
            seen["body"] = json
            return Response()

    monkeypatch.setattr("model_committee.providers.ollama.httpx.Client", Client)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")
    provider = OllamaWorkProvider(
        OllamaConfig(base_url="http://localhost:11434"),
        OllamaModelConfig(name="m"),
    )
    provider.generate_work_proposal(tmp_path, prompt, tmp_path / "schema.json")
    assert seen["url"] == "http://localhost:11434/api/generate"
    assert seen["body"]["think"] is False
    assert "think" not in seen["body"]["options"]


def test_config_rejects_nonlocal_ollama_base_url():
    with pytest.raises(ValueError):
        ModelCommitteeConfig.model_validate(
            {"ollama": {"base_url": "https://example.com", "models": []}}
        )
