"""Shared pytest fixtures."""
import pytest

from src.services.prescription import observability


@pytest.fixture(autouse=True)
def _reset_prescription_observability():
    """GH-84: the /prescribe idempotency cache, rate-limit budget, and
    counters are module-level shared state — reset between every test so one
    test's cached response / budget usage can't leak into another."""
    observability.reset()
    yield
    observability.reset()
