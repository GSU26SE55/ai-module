import threading

import pytest

from src.services import battery_history


@pytest.fixture(autouse=True)
def clear_history():
    """Each test gets a clean module-level store."""
    battery_history._history.clear()
    yield
    battery_history._history.clear()


class TestRecord:
    def test_missing_battery_id_is_noop(self):
        battery_history.record(None, 1.0, 90.0)
        battery_history.record("", 1.0, 90.0)
        assert battery_history._history == {}

    def test_missing_cycle_count_is_noop(self):
        battery_history.record("B0005", None, 90.0)
        assert battery_history._history == {}

    def test_records_append_per_battery(self):
        battery_history.record("B0005", 0.0, 100.0)
        battery_history.record("B0005", 1.0, 99.5)
        assert list(battery_history._history["B0005"]) == [(0.0, 100.0), (1.0, 99.5)]

    def test_bounded_history_evicts_oldest(self):
        for i in range(battery_history._MAXLEN + 3):
            battery_history.record("B0005", float(i), 100.0 - i)
        buf = battery_history._history["B0005"]
        assert len(buf) == battery_history._MAXLEN
        assert buf[0][0] == 3.0  # oldest 3 points evicted

    def test_separate_batteries_do_not_interfere(self):
        battery_history.record("B0005", 0.0, 100.0)
        battery_history.record("B0046", 0.0, 60.0)
        assert battery_history._history["B0005"][-1] == (0.0, 100.0)
        assert battery_history._history["B0046"][-1] == (0.0, 60.0)


class TestCausalRate:
    """causal_rate(battery_id, current_cycle, current_soh, k) — current_cycle/
    current_soh are the IN-FLIGHT request's own values (not yet recorded),
    compared against a point already recorded from a PRIOR request. Call
    BEFORE record() for the current request."""

    def test_no_history_returns_none(self):
        assert battery_history.causal_rate("B0005", 2.0, 90.0, k=2) is None

    def test_missing_battery_id_returns_none(self):
        battery_history.record("B0005", 0.0, 100.0)
        assert battery_history.causal_rate(None, 2.0, 90.0, k=2) is None
        assert battery_history.causal_rate("", 2.0, 90.0, k=2) is None

    def test_missing_current_cycle_returns_none(self):
        battery_history.record("B0005", 0.0, 100.0)
        assert battery_history.causal_rate("B0005", None, 90.0, k=2) is None

    def test_computes_expected_rate_against_single_prior_point(self):
        # prior: cycle 0 -> 100%. current (in-flight): cycle 2, soh 96%.
        # rate = (100-96)/2 = 2.0 %SOH/cycle
        battery_history.record("B0005", 0.0, 100.0)
        rate = battery_history.causal_rate("B0005", 2.0, 96.0, k=2)
        assert rate == pytest.approx(2.0)

    def test_k_selects_point_k_records_back(self):
        battery_history.record("B0005", 0.0, 100.0)
        battery_history.record("B0005", 1.0, 98.0)
        battery_history.record("B0005", 2.0, 96.0)
        # k=1 -> most recent prior record (cycle 2, soh 96); current cycle 3, soh 94
        # rate = (96-94)/(3-2) = 2.0
        rate = battery_history.causal_rate("B0005", 3.0, 94.0, k=1)
        assert rate == pytest.approx(2.0)

    def test_k_larger_than_history_clamps_to_oldest(self):
        battery_history.record("B0005", 0.0, 100.0)
        battery_history.record("B0005", 1.0, 99.0)
        # only 2 prior points, k=5 -> clamp to oldest available (cycle 0, soh 100)
        rate = battery_history.causal_rate("B0005", 3.0, 97.0, k=5)
        assert rate == pytest.approx(1.0)  # (100-97)/3

    def test_non_increasing_cycle_returns_none(self):
        battery_history.record("B0005", 5.0, 90.0)
        # current request's cycle <= the recorded prior cycle (retry/out-of-order)
        assert battery_history.causal_rate("B0005", 5.0, 89.0, k=1) is None
        assert battery_history.causal_rate("B0005", 4.0, 89.0, k=1) is None

    def test_slower_than_expected_gives_negative_rate(self):
        battery_history.record("B0005", 0.0, 90.0)
        # current SOH went UP vs prior (noise/charge cycle)
        rate = battery_history.causal_rate("B0005", 1.0, 90.5, k=1)
        assert rate < 0


class TestThreadSafety:
    def test_concurrent_record_no_crash_or_corruption(self):
        def worker(bid: str):
            for i in range(50):
                battery_history.record(bid, float(i), 100.0 - i * 0.1)

        threads = [
            threading.Thread(target=worker, args=(f"B{n}",)) for n in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for n in range(8):
            buf = battery_history._history[f"B{n}"]
            assert len(buf) == battery_history._MAXLEN
