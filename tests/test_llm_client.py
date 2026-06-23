"""Tests for the Anthropic LLM client (mocked SDK — no network, no API key needed)."""
import sys
import types

import pytest

from src.services import _llm_client


# ── Fake anthropic SDK ───────────────────────────────────────────────────────
class _Block:
    def __init__(self, type_, input_=None):
        self.type = type_
        self.input = input_


class _Resp:
    def __init__(self, content):
        self.content = content


def _make_fake_anthropic(response=None, raise_exc=None):
    mod = types.ModuleType("anthropic")

    class Anthropic:
        def __init__(self, **kwargs):
            self.messages = self

        def create(self, **kwargs):
            if raise_exc is not None:
                raise raise_exc
            return response

    mod.Anthropic = Anthropic
    return mod


# ── is_available ─────────────────────────────────────────────────────────────
def test_is_available_true(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert _llm_client.is_available() is True


def test_is_available_false(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert _llm_client.is_available() is False


# ── _format_docs ─────────────────────────────────────────────────────────────
def test_format_docs_empty():
    assert "(none retrieved)" in _llm_client._format_docs("Maintenance", [])


def test_format_docs_with_items():
    out = _llm_client._format_docs("Maintenance", [{"source": "x.md", "content": "do this"}])
    assert "x.md" in out and "do this" in out


# ── generate_prescription_llm ────────────────────────────────────────────────
def test_generate_raises_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        _llm_client.generate_prescription_llm("ctx", [], [])


def test_generate_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    resp = _Resp([_Block("tool_use", {
        "prescription": "Replace the battery.",
        "action_steps": ["Isolate", "Replace"],
        "ppe_required": ["Gloves"],
    })])
    monkeypatch.setitem(sys.modules, "anthropic", _make_fake_anthropic(response=resp))
    out = _llm_client.generate_prescription_llm(
        "SOH 68%", [{"source": "m.md", "content": "replace"}], [{"source": "s.md", "content": "loto"}],
    )
    assert out["prescription"] == "Replace the battery."
    assert out["action_steps"] == ["Isolate", "Replace"]
    assert out["ppe_required"] == ["Gloves"]


def test_generate_raises_on_api_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setitem(sys.modules, "anthropic", _make_fake_anthropic(raise_exc=Exception("503")))
    with pytest.raises(RuntimeError, match="Anthropic API call failed"):
        _llm_client.generate_prescription_llm("ctx", [], [])


def test_generate_raises_without_tool_use(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    resp = _Resp([_Block("text", None)])
    monkeypatch.setitem(sys.modules, "anthropic", _make_fake_anthropic(response=resp))
    with pytest.raises(RuntimeError, match="no tool_use"):
        _llm_client.generate_prescription_llm("ctx", [], [])


def test_generate_raises_on_malformed_output(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    resp = _Resp([_Block("tool_use", "not-a-dict")])
    monkeypatch.setitem(sys.modules, "anthropic", _make_fake_anthropic(response=resp))
    with pytest.raises(RuntimeError, match="malformed"):
        _llm_client.generate_prescription_llm("ctx", [], [])
