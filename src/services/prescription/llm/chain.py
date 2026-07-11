"""
LLM provider fallback chain — orchestrates DeepSeek -> Gemini -> (optional Anthropic).

Called by src.services.prescription.orchestrator._enrich() on enrich=true. Each provider
raises RuntimeError on failure; this module tries the next tier in order.
Bounded total wall-clock budget (~25s) so a slow/hung provider can't block an
event-driven call indefinitely — see docs/adr/0003-llm-provider-chain.md.

Config (env):
  LLM_PROVIDER_CHAIN — comma-separated provider names, default "deepseek,gemini".
                        "anthropic" can be added, e.g. "deepseek,gemini,anthropic".
"""
import logging
import os
import time

from src.services.prescription.llm.anthropic_provider import AnthropicProvider
from src.services.prescription.llm.deepseek_provider import DeepSeekProvider
from src.services.prescription.llm.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

DEFAULT_CHAIN = "deepseek,gemini"
TOTAL_BUDGET_S = 25.0
# GH-82: tighter budget for the query-gen step so the agentic path
# (query-gen + summarize) stays bounded well under 30s total.
QUERYGEN_BUDGET_S = 8.0

_PROVIDERS = {
    "deepseek": DeepSeekProvider,
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
}


def _chain_order() -> list[str]:
    raw = os.getenv("LLM_PROVIDER_CHAIN", DEFAULT_CHAIN)
    return [name.strip().lower() for name in raw.split(",") if name.strip()]


def is_available() -> bool:
    """True if at least one provider in the configured chain has a key set."""
    return any(
        _PROVIDERS[name]().is_available()
        for name in _chain_order()
        if name in _PROVIDERS
    )


def generate_prescription(
    context: str,
    maintenance_docs: list[dict],
    safety_docs: list[dict],
) -> dict:
    """
    Try each provider in LLM_PROVIDER_CHAIN order. Returns the first successful
    result with an added "provider" key. Raises RuntimeError if every provider
    is unavailable or fails — caller (orchestrator.py::_enrich) falls back to
    the rule-based prescription, exactly as it did for the single-provider path.
    """
    start = time.perf_counter()
    errors: list[str] = []

    for name in _chain_order():
        provider_cls = _PROVIDERS.get(name)
        if provider_cls is None:
            logger.warning("Unknown LLM provider %r in LLM_PROVIDER_CHAIN — skipping.", name)
            continue

        if time.perf_counter() - start > TOTAL_BUDGET_S:
            errors.append(f"{name}: skipped, total enrich budget ({TOTAL_BUDGET_S}s) exceeded")
            break

        provider = provider_cls()
        if not provider.is_available():
            continue

        try:
            out = provider.generate_prescription(context, maintenance_docs, safety_docs)
            out["provider"] = name
            return out
        except Exception as exc:  # provider's own RuntimeError, or anything unexpected
            logger.warning("LLM provider %r failed: %s", name, exc)
            errors.append(f"{name}: {exc}")

    raise RuntimeError(
        "All LLM providers unavailable or failed: "
        + ("; ".join(errors) if errors else "no provider configured")
    )


def judge_safety(context: str, action_steps: list[str]) -> dict:
    """
    GH-81 LLM-as-judge: try each provider in LLM_PROVIDER_CHAIN order and
    return the first successful verdict {"safe": bool, "reason": str,
    "provider": name}. Raises RuntimeError when every provider is
    unavailable or fails — the caller (orchestrator._run_judge) treats that
    as a pass so judge unavailability never blocks a rule-validated response.
    """
    start = time.perf_counter()
    errors: list[str] = []

    for name in _chain_order():
        provider_cls = _PROVIDERS.get(name)
        if provider_cls is None:
            logger.warning("Unknown LLM provider %r in LLM_PROVIDER_CHAIN — skipping.", name)
            continue

        if time.perf_counter() - start > TOTAL_BUDGET_S:
            errors.append(f"{name}: skipped, total judge budget ({TOTAL_BUDGET_S}s) exceeded")
            break

        provider = provider_cls()
        if not provider.is_available():
            continue

        try:
            out = provider.judge_safety(context, action_steps)
            out["provider"] = name
            return out
        except Exception as exc:  # provider's own RuntimeError, or anything unexpected
            logger.warning("LLM judge provider %r failed: %s", name, exc)
            errors.append(f"{name}: {exc}")

    raise RuntimeError(
        "All LLM judge providers unavailable or failed: "
        + ("; ".join(errors) if errors else "no provider configured")
    )


def generate_queries(diagnosis: str, budget_s: float | None = None) -> dict:
    """
    GH-82 agentic step 2: try each provider in LLM_PROVIDER_CHAIN order and
    return the first successful query set {"maintenance_queries": [str],
    "safety_queries": [str], "provider": name}. Raises RuntimeError when every
    provider is unavailable or fails — the caller (orchestrator) falls back to
    the template query, the pipeline never dies here.

    budget_s: wall-clock budget for the whole chain loop (default
    TOTAL_BUDGET_S) — the orchestrator passes QUERYGEN_BUDGET_S so query-gen
    can't eat the summarize step's time.
    """
    limit = TOTAL_BUDGET_S if budget_s is None else budget_s
    start = time.perf_counter()
    errors: list[str] = []

    for name in _chain_order():
        provider_cls = _PROVIDERS.get(name)
        if provider_cls is None:
            logger.warning("Unknown LLM provider %r in LLM_PROVIDER_CHAIN — skipping.", name)
            continue

        if time.perf_counter() - start > limit:
            errors.append(f"{name}: skipped, query-gen budget ({limit}s) exceeded")
            break

        provider = provider_cls()
        if not provider.is_available():
            continue

        try:
            out = provider.generate_queries(diagnosis)
            out["provider"] = name
            return out
        except Exception as exc:  # provider's own RuntimeError, or anything unexpected
            logger.warning("LLM query-gen provider %r failed: %s", name, exc)
            errors.append(f"{name}: {exc}")

    raise RuntimeError(
        "All LLM query-gen providers unavailable or failed: "
        + ("; ".join(errors) if errors else "no provider configured")
    )
