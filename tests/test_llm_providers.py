"""Tests for the LLM provider chain (GH-79) — mocked SDKs, no network, no real keys."""
import sys
import types
from unittest.mock import patch

import pytest

from src.services.prescription.llm import chain
from src.services.prescription.llm.anthropic_provider import AnthropicProvider
from src.services.prescription.llm.base import build_user_content, format_docs
from src.services.prescription.llm.deepseek_provider import DeepSeekProvider
from src.services.prescription.llm.gemini_provider import GeminiProvider


# ── Shared base helpers ─────────────────────────────────────────────────────
def test_format_docs_empty():
    assert "(none retrieved)" in format_docs("Maintenance", [])


def test_format_docs_with_items():
    out = format_docs("Maintenance", [{"source": "x.md", "content": "do this"}])
    assert "x.md" in out and "do this" in out


def test_build_user_content_includes_docs():
    out = build_user_content(
        "SOH 68%",
        [{"source": "m.md", "content": "replace battery"}],
        [{"source": "s.md", "content": "wear gloves"}],
    )
    assert "SOH 68%" in out
    assert "m.md" in out and "replace battery" in out
    assert "s.md" in out and "wear gloves" in out


# ── Fake Anthropic SDK ────────────────────────────────────────────────────
class _AnthropicBlock:
    def __init__(self, type_, input_=None):
        self.type = type_
        self.input = input_


class _AnthropicResp:
    def __init__(self, content):
        self.content = content


def _install_fake_anthropic(monkeypatch, response=None, raise_exc=None):
    mod = types.ModuleType("anthropic")

    class Anthropic:
        def __init__(self, **kwargs):
            self.messages = self

        def create(self, **kwargs):
            if raise_exc is not None:
                raise raise_exc
            return response

    mod.Anthropic = Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", mod)


# ── Anthropic provider ─────────────────────────────────────────────────────
def test_anthropic_is_available(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert AnthropicProvider().is_available() is True


def test_anthropic_not_available_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert AnthropicProvider().is_available() is False


def test_anthropic_generate_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    resp = _AnthropicResp([_AnthropicBlock("tool_use", {
        "prescription": "Replace the battery.",
        "action_steps": ["Isolate", "Replace"],
        "ppe_required": ["Gloves"],
    })])
    _install_fake_anthropic(monkeypatch, response=resp)
    out = AnthropicProvider().generate_prescription("SOH 68%", [], [])
    assert out["prescription"] == "Replace the battery."
    assert out["action_steps"] == ["Isolate", "Replace"]
    assert out["ppe_required"] == ["Gloves"]


def test_anthropic_generate_raises_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider().generate_prescription("ctx", [], [])


def test_anthropic_generate_raises_on_api_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    _install_fake_anthropic(monkeypatch, raise_exc=Exception("503"))
    with pytest.raises(RuntimeError, match="Anthropic API call failed"):
        AnthropicProvider().generate_prescription("ctx", [], [])


def test_anthropic_generate_raises_on_malformed_output(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    resp = _AnthropicResp([_AnthropicBlock("tool_use", "not-a-dict")])
    _install_fake_anthropic(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="malformed"):
        AnthropicProvider().generate_prescription("ctx", [], [])


def test_anthropic_generate_raises_on_no_tool_use_block(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    resp = _AnthropicResp([_AnthropicBlock("text", None)])
    _install_fake_anthropic(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="no tool_use"):
        AnthropicProvider().generate_prescription("ctx", [], [])


# ── Fake OpenAI (DeepSeek) SDK ─────────────────────────────────────────────
class _ToolCall:
    def __init__(self, arguments):
        self.function = types.SimpleNamespace(arguments=arguments)


def _install_fake_openai(monkeypatch, response=None, raise_exc=None):
    mod = types.ModuleType("openai")

    class _Completions:
        def create(self, **kwargs):
            if raise_exc is not None:
                raise raise_exc
            return response

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class OpenAI:
        def __init__(self, **kwargs):
            self.chat = _Chat()

    mod.OpenAI = OpenAI
    monkeypatch.setitem(sys.modules, "openai", mod)


def _fake_chat_response(arguments_json):
    message = types.SimpleNamespace(tool_calls=[_ToolCall(arguments_json)])
    choice = types.SimpleNamespace(message=message)
    return types.SimpleNamespace(choices=[choice])


# ── DeepSeek provider ────────────────────────────────────────────────────
def test_deepseek_is_available(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert DeepSeekProvider().is_available() is True


def test_deepseek_not_available_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert DeepSeekProvider().is_available() is False


def test_deepseek_generate_success(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    resp = _fake_chat_response(
        '{"prescription": "Replace it", "action_steps": ["a"], "ppe_required": ["Gloves"]}'
    )
    _install_fake_openai(monkeypatch, response=resp)
    out = DeepSeekProvider().generate_prescription("ctx", [], [])
    assert out["prescription"] == "Replace it"
    assert out["action_steps"] == ["a"]
    assert out["ppe_required"] == ["Gloves"]


def test_deepseek_generate_raises_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        DeepSeekProvider().generate_prescription("ctx", [], [])


def test_deepseek_generate_raises_on_api_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    _install_fake_openai(monkeypatch, raise_exc=Exception("503"))
    with pytest.raises(RuntimeError, match="DeepSeek API call failed"):
        DeepSeekProvider().generate_prescription("ctx", [], [])


def test_deepseek_generate_raises_on_no_tool_call(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    message = types.SimpleNamespace(tool_calls=None)
    choice = types.SimpleNamespace(message=message)
    resp = types.SimpleNamespace(choices=[choice])
    _install_fake_openai(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="no tool call"):
        DeepSeekProvider().generate_prescription("ctx", [], [])


def test_deepseek_generate_raises_on_malformed_json(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    resp = _fake_chat_response("not-json")
    _install_fake_openai(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="malformed"):
        DeepSeekProvider().generate_prescription("ctx", [], [])


def test_deepseek_generate_raises_on_missing_prescription_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    resp = _fake_chat_response('{"foo": "bar"}')
    _install_fake_openai(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="malformed"):
        DeepSeekProvider().generate_prescription("ctx", [], [])


# ── Fake google-genai (Gemini) SDK ─────────────────────────────────────────
def _install_fake_genai(monkeypatch, response=None, raise_exc=None):
    class _Models:
        def generate_content(self, **kwargs):
            if raise_exc is not None:
                raise raise_exc
            return response

    class Client:
        def __init__(self, **kwargs):
            self.models = _Models()

    genai_mod = types.ModuleType("google.genai")
    genai_mod.Client = Client
    google_mod = types.ModuleType("google")
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)


# ── Gemini provider ──────────────────────────────────────────────────────
def test_gemini_is_available(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-test")
    assert GeminiProvider().is_available() is True


def test_gemini_not_available_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert GeminiProvider().is_available() is False


def test_gemini_generate_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-test")
    resp = types.SimpleNamespace(
        text='{"prescription": "Replace it", "action_steps": ["a"], "ppe_required": ["Gloves"]}'
    )
    _install_fake_genai(monkeypatch, response=resp)
    out = GeminiProvider().generate_prescription("ctx", [], [])
    assert out["prescription"] == "Replace it"
    assert out["ppe_required"] == ["Gloves"]


def test_gemini_generate_raises_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiProvider().generate_prescription("ctx", [], [])


def test_gemini_generate_raises_on_api_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-test")
    _install_fake_genai(monkeypatch, raise_exc=Exception("503"))
    with pytest.raises(RuntimeError, match="Gemini API call failed"):
        GeminiProvider().generate_prescription("ctx", [], [])


def test_gemini_generate_raises_on_malformed_json(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-test")
    resp = types.SimpleNamespace(text="not-json")
    _install_fake_genai(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="malformed"):
        GeminiProvider().generate_prescription("ctx", [], [])


def test_gemini_generate_raises_on_missing_prescription_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-test")
    resp = types.SimpleNamespace(text='{"foo": "bar"}')
    _install_fake_genai(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="malformed"):
        GeminiProvider().generate_prescription("ctx", [], [])


def test_gemini_generate_raises_on_empty_text(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-test")
    resp = types.SimpleNamespace(text="")
    _install_fake_genai(monkeypatch, response=resp)
    with pytest.raises(RuntimeError, match="no text"):
        GeminiProvider().generate_prescription("ctx", [], [])


# ── Chain fallback (DeepSeek -> Gemini -> rule-based via caller) ───────────
class TestChainFallback:
    def test_is_available_true_when_any_key_set(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "key-test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert chain.is_available() is True

    def test_is_available_false_when_no_key(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert chain.is_available() is False

    def test_deepseek_fail_falls_to_gemini(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "key-test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with (
            patch.object(
                DeepSeekProvider, "generate_prescription",
                side_effect=RuntimeError("DeepSeek down"),
            ),
            patch.object(
                GeminiProvider, "generate_prescription",
                return_value={"prescription": "from gemini", "action_steps": [], "ppe_required": []},
            ),
        ):
            out = chain.generate_prescription("ctx", [], [])
        assert out["provider"] == "gemini"
        assert out["prescription"] == "from gemini"

    def test_malformed_output_jumps_to_next_tier(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "key-test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with (
            patch.object(
                DeepSeekProvider, "generate_prescription",
                side_effect=RuntimeError("DeepSeek returned malformed tool output."),
            ),
            patch.object(
                GeminiProvider, "generate_prescription",
                return_value={"prescription": "from gemini", "action_steps": [], "ppe_required": []},
            ),
        ):
            out = chain.generate_prescription("ctx", [], [])
        assert out["provider"] == "gemini"

    def test_both_fail_raises_runtime_error(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "key-test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with (
            patch.object(
                DeepSeekProvider, "generate_prescription",
                side_effect=RuntimeError("DeepSeek down"),
            ),
            patch.object(
                GeminiProvider, "generate_prescription",
                side_effect=RuntimeError("Gemini down"),
            ),
        ):
            with pytest.raises(RuntimeError, match="All LLM providers"):
                chain.generate_prescription("ctx", [], [])

    def test_no_key_configured_raises(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="All LLM providers"):
            chain.generate_prescription("ctx", [], [])

    def test_anthropic_included_when_configured_in_chain(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_PROVIDER_CHAIN", "deepseek,gemini,anthropic")

        with patch.object(
            AnthropicProvider, "generate_prescription",
            return_value={"prescription": "from anthropic", "action_steps": [], "ppe_required": []},
        ):
            out = chain.generate_prescription("ctx", [], [])
        assert out["provider"] == "anthropic"

    def test_unknown_provider_name_skipped(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER_CHAIN", "bogus,deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch.object(
            DeepSeekProvider, "generate_prescription",
            return_value={"prescription": "ok", "action_steps": [], "ppe_required": []},
        ):
            out = chain.generate_prescription("ctx", [], [])
        assert out["provider"] == "deepseek"

    def test_budget_exceeded_skips_remaining_tiers(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "key-test")
        monkeypatch.setattr(chain, "TOTAL_BUDGET_S", -1.0)
        with pytest.raises(RuntimeError, match="budget"):
            chain.generate_prescription("ctx", [], [])

    def test_anthropic_not_tried_by_default_chain(self, monkeypatch):
        """Default LLM_PROVIDER_CHAIN is deepseek,gemini — Anthropic must be
        explicitly opted into the chain, matching docs/adr/0003."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.delenv("LLM_PROVIDER_CHAIN", raising=False)

        assert chain.is_available() is False
        with pytest.raises(RuntimeError, match="All LLM providers"):
            chain.generate_prescription("ctx", [], [])
