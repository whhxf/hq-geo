"""Behavioral positioning gates using isolated fact packs."""
import importlib.util
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_positioning.py"
SPEC = importlib.util.spec_from_file_location("positioning_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PositioningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack = self.root / "facts/product/example--product-example"
        self.pack.mkdir(parents=True)
        self.fact = {"id": "f1", "claim": "Example serves buyers", "category": "product", "status": "verified", "source_id": "s1", "source_locator": "document#section", "verified_at": "2026-09-28", "evidence_type": "official_source"}
        (self.pack / "manifest.json").write_text(json.dumps({"sources": [{"id": "s1", "locator": "document.md"}]}))
        self.write_facts([self.fact])
        self.data = {"schema_version": 1, "id": "example", "revision": 1, "fact_pack": "facts/product/example--product-example", "statement": "Example helps buyers compare products", "positioning": {name: {"text": name, "fact_ids": ["f1"]} for name in MODULE.FACETS}, "tags": [{"dimension": name, "status": "unknown", "text": "", "reason": "Not established", "fact_ids": []} for name in sorted(MODULE.DIMENSIONS)], "boundaries": [], "applications": [{"channel": "blog", "audience": "buyers", "scenario": "comparison", "problem": "evidence", "positioning_revision": 1, "used_fact_ids": ["f1"], "review": {"status": "pass", "reviewer": "editor", "note": "Reviewed audience and claim support"}}], "status": "ready"}
        (self.root / "article.md").write_text("Example helps buyers compare products")
        self.data["applications"][0]["artifact_path"] = "article.md"
        self.data["applications"][0]["review"]["artifact_sha256"] = hashlib.sha256((self.root / "article.md").read_bytes()).hexdigest()

    def write_facts(self, facts):
        (self.pack / "facts.jsonl").write_text("\n".join(json.dumps(fact) for fact in facts))

    def validate(self):
        return MODULE.validate_positioning(self.data, self.root)

    def test_ready_and_unknown_price(self):
        self.assertTrue(self.validate()["creation_ready"])

    def test_missing_fact_fails_even_in_draft(self):
        self.data["status"] = "draft"
        self.data["positioning"]["identity"]["fact_ids"] = ["absent"]
        self.assertEqual(self.validate()["verdict"], "FAIL")

    def test_stale_application_blocks_ready(self):
        self.data["applications"][0]["positioning_revision"] = 2
        self.assertFalse(self.validate()["creation_ready"])
        self.assertEqual(self.validate()["verdict"], "FAIL")

    def test_pending_review_can_save_draft_but_cannot_create(self):
        self.data["applications"][0]["review"]["status"] = "pending"
        self.assertEqual(self.validate()["verdict"], "FAIL")
        self.data["status"] = "draft"
        self.assertEqual(self.validate()["verdict"], "PASS")
        self.assertFalse(self.validate()["creation_ready"])

    def test_unverified_fact_cannot_support_ready(self):
        for field, value in (("status", "needs_confirmation"), ("evidence_type", "inference"), ("source_id", "absent"), ("source_locator", ""), ("verified_at", "")):
            with self.subTest(field=field):
                self.write_facts([{**self.fact, field: value}])
                self.assertFalse(self.validate()["creation_ready"])

    def test_prohibited_claim_only_in_boundaries(self):
        prohibited = {**self.fact, "id": "p1", "category": "boundary", "status": "prohibited_claim"}
        self.write_facts([self.fact, prohibited])
        self.data["boundaries"] = ["p1"]
        self.assertTrue(self.validate()["creation_ready"])
        self.data["applications"][0]["used_fact_ids"] = ["p1"]
        self.assertEqual(self.validate()["verdict"], "FAIL")

    def test_duplicate_fact_ids_fail(self):
        self.write_facts([self.fact, self.fact])
        self.assertEqual(self.validate()["verdict"], "FAIL")

    def test_duplicate_tags_fail(self):
        self.data["tags"][0] = self.data["tags"][1]
        self.assertEqual(self.validate()["verdict"], "FAIL")

    def test_pack_cannot_escape_facts(self):
        self.data["fact_pack"] = "facts/../../elsewhere"
        self.assertEqual(self.validate()["verdict"], "FAIL")

    def test_malformed_inputs_report_failure(self):
        for malformed in (None, [], "text", {"schema_version": [], "revision": True, "status": [], "fact_pack": {}, "positioning": [], "tags": [{"dimension": []}], "applications": [None]}):
            with self.subTest(value=malformed):
                self.assertEqual(MODULE.validate_positioning(malformed, self.root)["verdict"], "FAIL")

    def test_empty_facets_can_save_draft(self):
        self.data["positioning"]["advantage"] = {"text": "", "fact_ids": []}
        self.assertFalse(self.validate()["creation_ready"])
        self.data["status"] = "draft"
        self.assertEqual(self.validate()["verdict"], "PASS")

    def test_changed_artifact_invalidates_review(self):
        (self.root / "article.md").write_text("New unsupported claim")
        self.assertEqual(self.validate()["verdict"], "FAIL")
        self.data["status"] = "draft"
        self.assertEqual(self.validate()["verdict"], "PASS")
        self.assertFalse(self.validate()["creation_ready"])

    def test_missing_artifact_blocks_ready(self):
        self.data["applications"][0]["artifact_path"] = "missing.md"
        self.assertFalse(self.validate()["creation_ready"])

    def test_multiple_artifacts_in_same_channel(self):
        other = copy.deepcopy(self.data["applications"][0])
        other["artifact_path"] = "article-two.md"
        (self.root / "article-two.md").write_bytes((self.root / "article.md").read_bytes())
        self.data["applications"].append(other)
        self.assertTrue(self.validate()["creation_ready"])
        other["artifact_path"] = "article.md"
        self.assertEqual(self.validate()["verdict"], "FAIL")

    def test_unknown_evidence_and_missing_source_locator(self):
        self.write_facts([{**self.fact, "evidence_type": "made_up"}])
        self.assertFalse(self.validate()["creation_ready"])
        self.write_facts([self.fact])
        (self.pack / "manifest.json").write_text(json.dumps({"sources": [{"id": "s1"}]}))
        self.assertFalse(self.validate()["creation_ready"])

    def test_owner_statement_category_restricted(self):
        self.write_facts([{**self.fact, "evidence_type": "owner_statement", "category": "external_result"}])
        self.assertFalse(self.validate()["creation_ready"])
        self.write_facts([{**self.fact, "evidence_type": "owner_statement", "category": "product_intent"}])
        self.assertTrue(self.validate()["creation_ready"])

    def test_cli_require_ready_rejects_valid_draft(self):
        self.data["status"] = "draft"
        plan = self.root / "positioning.json"
        plan.write_text(json.dumps(self.data))
        command = [sys.executable, str(SCRIPT), str(plan), "--root", str(self.root)]
        saved = subprocess.run(command, capture_output=True, text=True)
        gate = subprocess.run(command + ["--require-ready"], capture_output=True, text=True)
        self.assertEqual(saved.returncode, 0)
        self.assertEqual(gate.returncode, 1)
        self.assertEqual(json.loads(gate.stdout)["verdict"], "PASS")

    def test_cli_finds_project_root_without_root_flag(self):
        """不传 --root 时，去项目根找事实包，不在系统根找。

        定位卡和它引用的事实包都在项目里。这个参数原先默认指向系统根，
        意味着站 1 那条校验命令照着文档敲必然 FAIL——而文档是对的，
        错的是默认值。跑一次就能发现，但没人跑得起来就不会有人发现。
        """
        (self.root / ".hq-geo.json").write_text(
            json.dumps({"slug": "example", "name": "Example"}), encoding="utf-8"
        )
        plan = self.root / "positioning.json"
        plan.write_text(json.dumps(self.data), encoding="utf-8")

        env = {**os.environ, "HQ_GEO_PROJECT": str(self.root)}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(plan)],
            capture_output=True,
            text=True,
            env=env,
            cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["verdict"], "PASS")

    def test_malformed_text_fields_fail_even_for_drafts(self):
        self.data["status"] = "draft"
        for container, field in ((self.data, "statement"), (self.data["positioning"]["identity"], "text"), (self.data["tags"][0], "text"), (self.data["tags"][0], "reason")):
            original = container[field]
            container[field] = {}
            self.assertEqual(self.validate()["verdict"], "FAIL")
            container[field] = original


if __name__ == "__main__":
    unittest.main()
