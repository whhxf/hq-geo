import hashlib
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SYSTEM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYSTEM))
from project import find_project  # noqa: E402

PROJECT = find_project()
SPEC = spec_from_file_location("handoff", SYSTEM / "capabilities/creative-handoff/scripts/handoff.py")
handoff = module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


def fixture_job() -> dict:
    """最小合法 CreativeJob。测试用合成对象，不依赖任何具体项目。"""
    return {
        "schema_version": 1,
        "job_id": "sample-job",
        "revision": 1,
        "source": {"idea_id": "sample-idea", "topic_id": "T-01", "content_id": "sample-T-01",
                   "production_brief_path": "/tmp/sample/brief.json"},
        "title": "样例", "objective": "样例", "audience": "样例",
        "target": {"platforms": ["douyin"], "aspect_ratio": "9:16", "duration_seconds": 30, "language": "zh-CN"},
        "strategy": {"mode": "auto", "requested_pack_ids": [], "allow_fallback": False},
        "inputs": {"fact_refs": [], "asset_refs": [], "script_path": "/tmp/sample/script.md"},
        "scenes": [{"id": "s1", "spoken": "样例", "visual_intent": "样例", "evidence_mode": "synthetic_concept"}],
        "constraints": {"prohibited_claims": [], "synthetic_media_policy": "allow_concept_only"},
        "deliverables": {"shared": [{"id": "master", "type": "video", "count": 1}],
                         "channels": {"douyin": [{"id": "douyin-video", "type": "video", "count": 1}]}},
        "production_units": [{"id": "master", "type": "video", "count": 1, "phase": "master", "satisfies": ["master"]}],
        "decision_policy": {"required_decisions": ["scope"], "cost_confirmation": "before_each_paid_batch"},
        "handoff": {"target_system": "external", "receipt_schema_path": "/tmp/sample/receipt.schema.json"},
    }


def discover_jobs() -> list:
    """发现 content/briefs/<idea>/<topic>/creative-job.json，不写死任何项目标识。"""
    return sorted((PROJECT / "content/briefs").glob("*/*/creative-job.json"))


class CreativeHandoffTest(unittest.TestCase):
    def test_fixture_job_is_valid(self):
        handoff.validate_job(fixture_job())

    def test_every_existing_job_is_valid(self):
        for path in discover_jobs():
            with self.subTest(job=str(path.relative_to(PROJECT))):
                job = handoff.load(path)
                handoff.validate_job(job)
                self.assertTrue(job["deliverables"]["channels"], f"{path} 缺少渠道交付矩阵")

    def test_missing_job_field_is_rejected(self):
        job = fixture_job()
        del job["source"]
        with self.assertRaisesRegex(ValueError, "source"):
            handoff.validate_job(job)

    def test_receipt_rejects_output_outside_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = {"schema_version": 1, "job_id": "j", "revision": 1, "content_id": "c", "status": "completed", "strategy": {"id": "p", "version": "1"}, "project_path": str(root / "project"), "outputs": [{"id": "o", "type": "image", "path": str(root / "outside.png"), "sha256": "x", "synthetic": True, "status": "completed"}], "checks": {"facts": "passed", "asset_rights": "passed", "platform_spec": "passed", "ai_disclosure": "required"}, "created_at": "2026-09-11T00:00:00+08:00"}
            with self.assertRaisesRegex(ValueError, "escapes"):
                handoff.validate_receipt(receipt, verify_files=False)

    def test_completed_output_checksum_is_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            media = project / "image.png"
            media.write_bytes(b"image")
            receipt = {"schema_version": 1, "job_id": "j", "revision": 1, "content_id": "c", "status": "completed", "strategy": {"id": "p", "version": "1"}, "project_path": str(project), "outputs": [{"id": "o", "type": "image", "path": str(media), "sha256": hashlib.sha256(b"image").hexdigest(), "synthetic": True, "status": "completed"}], "checks": {"facts": "passed", "asset_rights": "passed", "platform_spec": "passed", "ai_disclosure": "required"}, "created_at": "2026-09-11T00:00:00+08:00"}
            handoff.validate_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
