from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Scenario:
    action: str
    direct_cost_usd: int
    expected_delay_days: int
    requires_engineering_approval: bool = False

SCENARIOS = (
    Scenario("NORMAL", 0, 5),
    Scenario("EXPEDITE", 180, 0),
    Scenario("ALTERNATE_PART", 110, 1, True),
)

def rank_recovery(
    day_penalty_usd: int = 120,
    engineering_approved: bool = False,
    max_direct_cost_usd: int = 500,
) -> list[dict]:
    if day_penalty_usd < 0 or max_direct_cost_usd < 0:
        raise ValueError("Costs and penalty assumptions must be nonnegative")
    ranking = []
    for scenario in SCENARIOS:
        if scenario.direct_cost_usd > max_direct_cost_usd:
            continue
        if scenario.requires_engineering_approval and not engineering_approved:
            continue
        ranking.append({
            "action": scenario.action,
            "direct_cost_usd": scenario.direct_cost_usd,
            "expected_delay_days": scenario.expected_delay_days,
            "score_usd_equivalent": scenario.direct_cost_usd
                + scenario.expected_delay_days * day_penalty_usd,
            "illustrative_only": True,
        })
    return sorted(ranking, key=lambda s: (s["score_usd_equivalent"], s["direct_cost_usd"]))
