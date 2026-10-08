"""Conservative champion/challenger promotion policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionDecision:
    status: str
    reason: str


def evaluate_promotion(
    *,
    champion_score: float,
    challenger_score: float,
    champion_samples: int,
    challenger_samples: int,
    unseen_superior: bool,
    adversarial_pass: bool,
    regression_pass: bool,
    calibration_pass: bool,
    reliability_pass: bool,
    generalization_pass: bool,
    minimum_samples: int = 30,
    minimum_margin: float = 0.05,
) -> PromotionDecision:
    if min(champion_samples, challenger_samples) < minimum_samples:
        return PromotionDecision("RETAIN", "INSUFFICIENT_SAMPLE")
    if not all((unseen_superior, adversarial_pass, regression_pass, calibration_pass,
                reliability_pass, generalization_pass)):
        return PromotionDecision("RETAIN", "CHALLENGER_VALIDATION_INCOMPLETE")
    if challenger_score < champion_score + minimum_margin:
        return PromotionDecision("RETAIN", "NO_STATISTICALLY_MATERIAL_MARGIN")
    return PromotionDecision("PROMOTE", "CHALLENGER_VALIDATED")
