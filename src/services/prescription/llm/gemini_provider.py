"""
Gemini provider — native structured output via response_schema.

Backup provider in the LLM fallback chain (src.services.prescription.llm.chain), tried
after DeepSeek fails — see docs/adr/0003-llm-provider-chain.md.

Config (env):
  GEMINI_API_KEY  — required to use this provider.
  GEMINI_MODEL    — optional override (default: gemini-2.5-flash).
"""
import json
import os

from src.services.prescription.llm.base import (
    JUDGE_SCHEMA,
    JUDGE_SYSTEM_PROMPT,
    MAX_RETRIES,
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    TIMEOUT_S,
    LLMProvider,
    build_judge_content,
    build_user_content,
)

DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def is_available(self) -> bool:
        """True if an API key is configured (provider usable)."""
        return bool(os.getenv("GEMINI_API_KEY"))

    def generate_prescription(
        self,
        context: str,
        maintenance_docs: list[dict],
        safety_docs: list[dict],
    ) -> dict:
        """
        Call Gemini (native response_schema) to generate a structured prescription.

        Returns dict with keys: prescription, action_steps, ppe_required.
        Raises RuntimeError on missing key / API error / malformed output — the
        chain catches this and falls back to rule-based.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set — cannot use Gemini provider.")

        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("google-genai SDK not installed.") from exc

        user_content = build_user_content(context, maintenance_docs, safety_docs)

        client = genai.Client(api_key=api_key)
        # SDK's own retry config isn't guaranteed stable across versions — retry
        # manually (MAX_RETRIES extra attempts) to match the "1 retry per tier"
        # behavior the other providers get from their SDK's max_retries kwarg.
        last_exc: Exception | None = None
        resp = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
                    contents=user_content,
                    config={
                        "system_instruction": SYSTEM_PROMPT,
                        "response_mime_type": "application/json",
                        "response_schema": RESPONSE_SCHEMA,
                        "http_options": {"timeout": int(TIMEOUT_S * 1000)},
                    },
                )
                last_exc = None
                break
            except Exception as exc:  # google.genai errors, timeouts, etc.
                last_exc = exc
        if last_exc is not None:
            raise RuntimeError(f"Gemini API call failed: {last_exc}") from last_exc

        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("Gemini response contained no text.")

        try:
            out = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini returned malformed tool output.") from exc

        if not isinstance(out, dict) or "prescription" not in out:
            raise RuntimeError("Gemini returned malformed tool output.")

        return {
            "prescription": str(out.get("prescription", "")),
            "action_steps": list(out.get("action_steps", [])),
            "ppe_required": list(out.get("ppe_required", [])),
        }

    def judge_safety(self, context: str, action_steps: list[str]) -> dict:
        """
        GH-81 LLM-as-judge via Gemini native response_schema.

        Returns dict with keys: safe (bool), reason (str).
        Raises RuntimeError on missing key / API error / malformed output.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set — cannot use Gemini provider.")

        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("google-genai SDK not installed.") from exc

        client = genai.Client(api_key=api_key)
        # Manual retry for the same reason as generate_prescription above.
        last_exc: Exception | None = None
        resp = None
        for _attempt in range(MAX_RETRIES + 1):
            try:
                resp = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
                    contents=build_judge_content(context, action_steps),
                    config={
                        "system_instruction": JUDGE_SYSTEM_PROMPT,
                        "response_mime_type": "application/json",
                        "response_schema": JUDGE_SCHEMA,
                        "http_options": {"timeout": int(TIMEOUT_S * 1000)},
                    },
                )
                last_exc = None
                break
            except Exception as exc:  # google.genai errors, timeouts, etc.
                last_exc = exc
        if last_exc is not None:
            raise RuntimeError(f"Gemini API call failed: {last_exc}") from last_exc

        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("Gemini response contained no text.")

        try:
            out = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini returned malformed tool output.") from exc

        if not isinstance(out, dict) or "safe" not in out:
            raise RuntimeError("Gemini returned malformed tool output.")

        return {"safe": bool(out["safe"]), "reason": str(out.get("reason", ""))}
