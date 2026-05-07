import pytest

from model_committee.errors import ModelOutputError
from model_committee.responses.json_extract import extract_json_object


def test_extracts_whole_json():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extracts_single_fence():
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_rejects_multiple_fences():
    with pytest.raises(ModelOutputError):
        extract_json_object('```\n{"a": 1}\n```\n```\n{"b": 2}\n```')
