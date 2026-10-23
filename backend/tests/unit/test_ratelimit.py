"""Fase 10: limitador por ventana deslizante y validación de ``X-Request-ID``."""

from __future__ import annotations

from app.core.ratelimit import Limit, SlidingWindowLimiter
from app.core.request_context import accept_or_generate


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_allows_the_limit_and_reports_the_wait() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    rule = Limit(2, 60)
    assert limiter.hit("k", rule) is None
    clock.now += 10
    assert limiter.hit("k", rule) is None
    clock.now += 10
    assert limiter.hit("k", rule) == 40  # el primer evento sale de la ventana a los 60 s
    clock.now += 41
    assert limiter.hit("k", rule) is None


def test_keys_are_independent_and_rejected_hits_are_not_counted() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    rule = Limit(1, 60)
    assert limiter.hit("a", rule) is None
    assert limiter.hit("b", rule) is None
    for _ in range(5):
        assert limiter.hit("a", rule) is not None
    clock.now += 61
    assert limiter.hit("a", rule) is None


def test_blocked_and_record_count_only_failures() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    rule = Limit(2, 900)
    assert limiter.blocked("f", rule) is None
    limiter.record("f")
    assert limiter.blocked("f", rule) is None
    limiter.record("f")
    assert limiter.blocked("f", rule) == 900
    clock.now += 900
    assert limiter.blocked("f", rule) is None


def test_request_id_validation() -> None:
    assert accept_or_generate("abcdef-12") == "abcdef-12"
    for bad in (None, "", "short", "con espacio 123", "x" * 65, 'inyección"}'):
        assert len(accept_or_generate(bad)) == 26
