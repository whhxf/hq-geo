import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_fact_pack.py"
SPEC = importlib.util.spec_from_file_location("fact_validator", MODULE_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
CAPTURE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "capture_fact.py"
CAPTURE_SPEC = importlib.util.spec_from_file_location("fact_capture", CAPTURE_PATH)
CAPTURE = importlib.util.module_from_spec(CAPTURE_SPEC)
CAPTURE_SPEC.loader.exec_module(CAPTURE)


class FactPackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pack = Path(self.tmp.name) / "feature" / "demo--feature-demo"
        for folder in ("text", "media/images", "media/videos", "reviews"):
            (self.pack / folder).mkdir(parents=True, exist_ok=True)
        (self.pack / "SOURCE_OF_TRUTH.md").write_text("# Demo\n", encoding="utf-8")
        (self.pack / "text/overview.md").write_text("# Overview\n", encoding="utf-8")
        self.manifest = {
            "schema_version": 1,
            "id": "feature-demo",
            "entity_type": "feature",
            "slug": "demo",
            "name": "Demo",
            "required_slots": [{"id": "overview", "label": "概览", "kind": "document", "status": "present", "path": "text/overview.md", "fact_ids": ["fact-1"]}],
            "protected_fact_ids": ["fact-1"],
            "sources": [{"id": "source-1", "locator": "source.md"}],
            "media_assets": [],
            "pending_questions": [{"id": "q-1", "question": "What is true?", "reason": "Needed for copy", "target_category": "founder_viewpoint", "answer_policy": "owner_statement", "status": "pending", "priority": 1, "blocks": ["topic:T1"], "result_fact_ids": []}],
        }
        self.fact = {"id": "fact-1", "claim": "A fact", "category": "product", "evidence_type": "official_source", "status": "verified", "source_id": "source-1", "source_locator": "source.md#fact", "verified_at": "2026-09-09", "scope": "feature"}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        (self.pack / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        (self.pack / "facts.jsonl").write_text(json.dumps(self.fact) + "\n", encoding="utf-8")

    def test_valid_pack_passes(self):
        self.write()
        self.assertEqual(VALIDATOR.validate_pack(self.pack)["verdict"], "PASS")

    def test_unverified_inference_cannot_enter_as_verified(self):
        self.fact["evidence_type"] = "inference"
        self.write()
        report = VALIDATOR.validate_pack(self.pack)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("cannot be verified" in item for item in report["errors"]))

    def test_protected_fact_cannot_disappear(self):
        self.manifest["protected_fact_ids"] = ["confirmed-but-missing"]
        self.write()
        report = VALIDATOR.validate_pack(self.pack)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertIn("protected fact missing: confirmed-but-missing", report["errors"])

    def test_missing_media_is_visible_but_not_fabricated(self):
        self.manifest["required_slots"].append({"id": "walkthrough", "label": "操作视频", "kind": "video", "status": "missing", "asset_ids": ["video-1"]})
        self.manifest["media_assets"] = [{"id": "video-1", "kind": "video", "status": "missing", "path": None, "url": None}]
        self.write()
        report = VALIDATOR.validate_pack(self.pack)
        self.assertEqual(report["verdict"], "PASS")
        self.assertFalse(report["creation_ready"])
        self.assertIn("required slot missing: 操作视频", report["warnings"])

    def test_dialogue_answer_is_persisted_and_question_is_retained(self):
        self.write()
        result = CAPTURE.capture(self.pack, question_id="q-1", fact_id="fact-owner-1", claim="The founder prefers evidence first.", answer="先放证据。", category="founder_viewpoint")
        manifest = json.loads((self.pack / "manifest.json").read_text(encoding="utf-8"))
        facts = [json.loads(line) for line in (self.pack / "facts.jsonl").read_text(encoding="utf-8").splitlines()]
        changes = [json.loads(line) for line in (self.pack / "reviews/change-log.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(result["captured"], "fact-owner-1")
        self.assertEqual(manifest["pending_questions"][0]["status"], "resolved")
        self.assertIn("fact-owner-1", manifest["protected_fact_ids"])
        self.assertEqual(facts[-1]["evidence_type"], "owner_statement")
        self.assertEqual(changes[-1]["answer_original"], "先放证据。")
        self.assertEqual(VALIDATOR.validate_pack(self.pack)["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
