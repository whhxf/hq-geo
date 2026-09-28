import unittest

from capabilities.geo.scripts.validate_pack import load_manifest, validate_pack


class GeoCapabilityPackTest(unittest.TestCase):
    def test_pack_is_valid(self) -> None:
        self.assertEqual(validate_pack(), [])

    def test_social_defaults_are_lightweight(self) -> None:
        manifest = load_manifest()
        self.assertEqual(
            manifest["lightweight_social_guards"],
            [
                "verifiable_claims",
                "entity_consistency",
                "accurate_one_sentence_thesis",
            ],
        )
        self.assertIn("schema_required", manifest["never_global_defaults"])
        self.assertIn("faq_required", manifest["never_global_defaults"])

    def test_full_geo_and_social_routes_are_separate(self) -> None:
        manifest = load_manifest()
        self.assertIn("owned_website_content", manifest["full_geo_routes"])
        self.assertIn("ai_citation_or_visibility", manifest["full_geo_routes"])
        self.assertNotIn("social_content", manifest["full_geo_routes"])
        self.assertIn(
            "guaranteed_ai_citation", manifest["never_global_defaults"]
        )

    def test_attribution_is_a_declared_capability(self) -> None:
        manifest = load_manifest()
        self.assertEqual(
            manifest["attribution_contract"],
            "capabilities/geo/contracts/geo-attribution-plan.schema.json",
        )
        self.assertIn(
            "capabilities/geo/methods/measurement-attribution-and-roi.md",
            manifest["method_sources"],
        )
        self.assertIn("geo-attribution", [item["name"] for item in manifest["skills"]])

    def test_positioning_contract_is_declared(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["positioning_contract"], "capabilities/geo/contracts/positioning.schema.json")
        self.assertIn("capabilities/geo/methods/positioning-and-audience.md", manifest["method_sources"])


if __name__ == "__main__":
    unittest.main()
