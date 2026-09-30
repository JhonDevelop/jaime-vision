"""Gate numérico simples para uma proposta de modelo/tracker."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Metrics:
    accuracy: float
    false_activations_per_hour: float
    p95_ms: float
    sample_count: int

def assess(baseline: Metrics, candidate: Metrics, *, min_samples: int = 100,
           max_p95_regression: float = .05) -> tuple[bool, str]:
    if baseline.sample_count < min_samples or candidate.sample_count < min_samples:
        return False, "insufficient replay samples"
    if candidate.accuracy < baseline.accuracy:
        return False, "accuracy regression"
    if candidate.false_activations_per_hour > baseline.false_activations_per_hour:
        return False, "false activations regression"
    if candidate.p95_ms > baseline.p95_ms * (1 + max_p95_regression):
        return False, "latency regression"
    return True, "candidate passes numerical gates; deployment policy still applies"
