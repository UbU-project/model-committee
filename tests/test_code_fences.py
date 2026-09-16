from model_committee.consistency.code_fences import code_fence_warnings


def _codes(text: str) -> list[str]:
    return [issue.code for issue in code_fence_warnings("DECISIONS.md", text)]


def test_closed_fences_have_no_warnings():
    text = """## UBU-D0001: First

```text
LLM output -> validation
```

````markdown
```text
nested
```
````

## UBU-D0002: Second
"""
    assert _codes(text) == []


def test_unclosed_fence_with_even_fence_count_is_detected():
    # Four fence lines pair up by count, but the first block is never closed: the
    # second ```text cannot close it, so its closing ``` does and D0002 is swallowed.
    text = """## UBU-D0001: First

```text
a -> b

## UBU-D0002: Second

```text
c -> d
```

## UBU-D0003: Third

```text
e
```
"""
    issues = code_fence_warnings("DECISIONS.md", text)
    assert [issue.code for issue in issues] == [
        "HEADING_INSIDE_CODE_FENCE",
        "CODE_FENCE_UNCLOSED",
    ]
    assert issues[0].decision_id == "UBU-D0002"
    assert "DECISIONS.md:6" in issues[0].message
    assert "opened at line 3" in issues[0].message


def test_fence_open_at_end_of_file_is_detected():
    text = "## UBU-Q0001: First\n\n```text\nunfinished\n\n## UBU-Q0002: Second\n"
    issues = code_fence_warnings("OPEN_QUESTIONS.md", text)
    assert [issue.code for issue in issues] == [
        "HEADING_INSIDE_CODE_FENCE",
        "CODE_FENCE_UNCLOSED",
    ]
    assert issues[0].question_id == "UBU-Q0002"
    assert issues[1].message == "OPEN_QUESTIONS.md:3 code fence is never closed."
