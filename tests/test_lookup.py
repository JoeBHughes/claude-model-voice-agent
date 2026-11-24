"""Tests for the model lookup logic in src/agent.py.

These tests need no microphone and no LiveKit account. An automated test
runner (pytest) calls the lookup functions directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import agent  # noqa: E402


def test_spoken_forms_find_the_same_model():
    for name in ["Opus 4.8", "opus four point eight", "opus 48", "claude-opus-4-8"]:
        assert "claude-opus-4-8 is released and available" in agent.check_model_text(name)


def test_older_word_order():
    assert "claude-3-5-haiku-20241022" in agent.check_model_text("haiku 3.5")


def test_family_and_version_prefer_exact_match():
    result = agent.check_model_text("opus 4")
    assert "claude-opus-4-20250514" in result
    assert "claude-opus-4-8 is released" not in result


def test_retired_model_names_replacement():
    result = agent.check_model_text("claude 3 haiku")
    assert "retired" in result
    assert "claude-haiku-4-5-20251001" in result


def test_unknown_model_is_not_guessed():
    assert "can't confirm" in agent.check_model_text("opus 6")


def test_every_answer_names_its_source():
    for name in ["sonnet 4.5", "opus 6"]:
        assert "Anthropic's model deprecations page" in agent.check_model_text(name)
    assert "Anthropic's model deprecations page" in agent.retiring_text()
