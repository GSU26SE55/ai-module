"""
Anthropic Claude provider — forced tool-use, structured prescription output.

One tier in the LLM fallback chain (src.services.prescription.llm.chain). Kept as an
optional provider for backward compat with GH-20/22 — no longer the default
chain (see docs/adr/0003-llm-provider-chain.md), but still usable via
LLM_PROVIDER_CHAIN=...,anthropic.

Config (env):
  ANTHROPIC_API_KEY  — required to use this provider.
  ANTHROPIC_MODEL    — optional override (default: claude-haiku-4-5-20251001).
"""
import os

from src.services.prescription.llm.base import (
    JUDGE_SCHEMA,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_TOOL_DESCRIPTION,
    JUDGE_TOOL_NAME,
    MAX_RETRIES,
    QUERYGEN_SCHEMA,
    QUERYGEN_SYSTEM_PROMPT,
    QUERYGEN_TOOL_DESCRIPTION,
    QUERYGEN_TOOL_NAME,
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    TIMEOUT_S,
    TOOL_DESCRIPTION,
    TOOL_NAME,
    LLMProvider,
    build_judge_content,
    build_querygen_content,
    build_user_content,
)

# Default to Claude Haiku 4.5 — cheap/fast, sufficient for short structured output.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 512


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def is_available(self) -> bool:
        """True if an API key is configured (provider usable)."""
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def generate_prescription(
        self,
        context: str,
        maintenance_docs: list[dict],
        safety_docs: list[dict],
        past_cases: list[dict] | None = None,
    ) -> dict:
        """
        Call Claude to generate a structured prescription.

        Returns dict with keys: prescription, action_steps, ppe_required.
        Raises RuntimeError on missing key / API error / malformed output — the
        chain catches this and tries the next provider.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — cannot use Anthropic provider.")

        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("anthropic SDK not installed.") from exc

        tool = {
            "name": TOOL_NAME,
            "description": TOOL_DESCRIPTION,
            "input_schema": RESPONSE_SCHEMA,
        }
        user_content = build_user_content(context, maintenance_docs, safety_docs, past_cases)

        client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_S, max_retries=MAX_RETRIES)
        try:
            resp = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=[tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as exc:  # anthropic.APIError, timeouts, etc.
            raise RuntimeError(f"Anthropic API call failed: {exc}") from exc

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                out = block.input
                if not isinstance(out, dict) or "prescription" not in out:
                    raise RuntimeError("LLM returned malformed tool output.")
                return {
                    "prescription": str(out.get("prescription", "")),
                    "action_steps": list(out.get("action_steps", [])),
                    "ppe_required": list(out.get("ppe_required", [])),
                }

        raise RuntimeError("LLM response contained no tool_use block.")

    def judge_safety(self, context: str, action_steps: list[str]) -> dict:
        """
        GH-81 LLM-as-judge via Claude forced tool-use.

        Returns dict with keys: safe (bool), reason (str).
        Raises RuntimeError on missing key / API error / malformed output.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — cannot use Anthropic provider.")

        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("anthropic SDK not installed.") from exc

        tool = {
            "name": JUDGE_TOOL_NAME,
            "description": JUDGE_TOOL_DESCRIPTION,
            "input_schema": JUDGE_SCHEMA,
        }

        client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_S, max_retries=MAX_RETRIES)
        try:
            resp = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
                max_tokens=MAX_TOKENS,
                system=JUDGE_SYSTEM_PROMPT,
                tools=[tool],
                tool_choice={"type": "tool", "name": JUDGE_TOOL_NAME},
                messages=[
                    {"role": "user", "content": build_judge_content(context, action_steps)}
                ],
            )
        except Exception as exc:  # anthropic.APIError, timeouts, etc.
            raise RuntimeError(f"Anthropic API call failed: {exc}") from exc

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                out = block.input
                if not isinstance(out, dict) or "safe" not in out:
                    raise RuntimeError("LLM returned malformed tool output.")
                return {"safe": bool(out["safe"]), "reason": str(out.get("reason", ""))}

        raise RuntimeError("LLM response contained no tool_use block.")

    def generate_queries(self, diagnosis: str) -> dict:
        """
        GH-82 query generation via Claude forced tool-use.

        Returns dict with keys: maintenance_queries, safety_queries (list[str]).
        Raises RuntimeError on missing key / API error / malformed output.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — cannot use Anthropic provider.")

        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("anthropic SDK not installed.") from exc

        tool = {
            "name": QUERYGEN_TOOL_NAME,
            "description": QUERYGEN_TOOL_DESCRIPTION,
            "input_schema": QUERYGEN_SCHEMA,
        }

        client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_S, max_retries=MAX_RETRIES)
        try:
            resp = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
                max_tokens=MAX_TOKENS,
                system=QUERYGEN_SYSTEM_PROMPT,
                tools=[tool],
                tool_choice={"type": "tool", "name": QUERYGEN_TOOL_NAME},
                messages=[{"role": "user", "content": build_querygen_content(diagnosis)}],
            )
        except Exception as exc:  # anthropic.APIError, timeouts, etc.
            raise RuntimeError(f"Anthropic API call failed: {exc}") from exc

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                out = block.input
                if not isinstance(out, dict) or "maintenance_queries" not in out:
                    raise RuntimeError("LLM returned malformed tool output.")
                return {
                    "maintenance_queries": [str(q) for q in out.get("maintenance_queries", [])],
                    "safety_queries": [str(q) for q in out.get("safety_queries", [])],
                }

        raise RuntimeError("LLM response contained no tool_use block.")
