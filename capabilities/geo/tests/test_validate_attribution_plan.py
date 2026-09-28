import copy
import unittest
from pathlib import Path

from capabilities.geo.scripts.validate_attribution_plan import load_plan, validate_plan


ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "capabilities/geo/examples/attribution-plan.example.json"


class GeoAttributionPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = load_plan(EXAMPLE)

    def test_example_is_valid(self) -> None:
        self.assertEqual(validate_plan(self.plan), [])

    def test_requires_deduplication_key(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["deduplication"]["entity_key"] = ""
        self.assertIn("deduplication.entity_key is required", validate_plan(plan))

    def test_rejects_revenue_basis_for_profit_objective(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["objective"] = "contribution_margin"
        plan["economics"]["value_basis"] = "revenue"
        self.assertIn(
            "contribution_margin objective requires contribution_margin value_basis",
            validate_plan(plan),
        )

    def test_experimental_marker_requires_experiment(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["markers"][0]["evidence_tier"] = "experimental"
        plan["experiment"] = None
        self.assertIn(
            "experimental evidence requires an experiment definition",
            validate_plan(plan),
        )

    def test_baseline_must_precede_treatment(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["observation_window"]["treatment_start"] = "2026-09-30"
        self.assertIn("baseline must end before treatment starts", validate_plan(plan))


if __name__ == "__main__":
    unittest.main()
