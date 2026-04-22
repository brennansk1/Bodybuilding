from __future__ import annotations

"""
Shared typed primitives for the constants layer.

Engines that report measurements, ceilings, or thresholds with known
uncertainty should carry (value, sigma, source) rather than a bare float.
This is deliberately light — a dataclass, not a Pydantic type — because
it lives in the constants layer and the rest of the engines treat
numbers as numbers. The `.value` accessor lets any consumer unwrap.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValueWithUncertainty:
    """A physiological/statistical constant with an associated provenance.

    value: point estimate
    sigma: one-standard-deviation uncertainty (None if unknown)
    source: short citation string ("Helms 2014", "Kouri 1995", etc.)
    notes: free-form clarification when the source is insufficient alone.
    """
    value: float
    sigma: float | None = None
    source: str = ""
    notes: str = ""

    def __float__(self) -> float:
        return float(self.value)

    def ci95(self) -> tuple[float, float] | None:
        if self.sigma is None:
            return None
        return (self.value - 1.96 * self.sigma, self.value + 1.96 * self.sigma)
