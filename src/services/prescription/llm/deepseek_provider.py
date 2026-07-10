"""
DeepSeek provider — OpenAI-compatible API, function calling for structured output.

Primary provider in the LLM fallback chain (src.services.prescription.llm.chain) as of
GH-79 / docs/adr/0003-llm-provider-chain.md.

Config (env):
  DEEPSEEK_API_KEY  — required to use this provider.
  DEEPSEEK_MODEL    — optional override (default: deepseek-chat).
"""
import json
import os

from src.services.prescription.llm.base import (
    MAX_RETRIES,
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    TIMEOUT_S,
    TOOL_DESCRIPTION,
    TOOL_NAME,
    LLMProvider,
    build_user_content,
)

DEFAULT_MODEL = "deepseek-chat"
MAX_TOKENS = 512
BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def is_available(self) -> bool:
        """True if an API key is configured (provider usable)."""
        return bool(os.getenv("DEEPSEEK_API_KEY"))

    def generate_prescription(
        self,
        context: str,
        maintenance_docs: list[dict],
        safety_docs: list[dict],
    ) -> dict:
        """
        Call DeepSeek (OpenAI-compatible function calling) to generate a
        structured prescription.

        Returns dict with keys: prescription, action_steps, ppe_required.
        Raises RuntimeError on missing key / API error / malformed output — the
        chain catches this and tries the next provider.
        """
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set — cannot use DeepSeek provider.")

        try:
            import openai
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("openai SDK not installed.") from exc

        tool = {
            "type": "function",
            "function": {
                "name": TOOL_NAME,
                "description": TOOL_DESCRIPTION,
                "parameters": RESPONSE_SCHEMA,
            },
        }
        user_content = build_user_content(context, maintenance_docs, safety_docs)

        client = openai.OpenAI(
            api_key=api_key, base_url=BASE_URL, timeout=TIMEOUT_S, max_retries=MAX_RETRIES
        )
        try:
            resp = client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
            )
        except Exception as exc:  # openai.APIError, timeouts, etc.
            raise RuntimeError(f"DeepSeek API call failed: {exc}") from exc

        tool_calls = resp.choices[0].message.tool_calls if resp.choices else None
        if not tool_calls:
            raise RuntimeError("DeepSeek response contained no tool call.")

        try:
            out = json.loads(tool_calls[0].function.arguments)
        except (json.JSONDecodeError, AttributeError, IndexError) as exc:
            raise RuntimeError("DeepSeek returned malformed tool output.") from exc

        if not isinstance(out, dict) or "prescription" not in out:
            raise RuntimeError("DeepSeek returned malformed tool output.")

        return {
            "prescription": str(out.get("prescription", "")),
            "action_steps": list(out.get("action_steps", [])),
            "ppe_required": list(out.get("ppe_required", [])),
        }
