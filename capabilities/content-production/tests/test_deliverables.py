"""交付契约的单测。

**只用 fixture，不读任何项目根。** 2026-10-10 起门禁不依赖项目，
原先「遍历项目里每个简报」的两条用例移出门禁——那是项目侧的验收，
由项目自己跑。契约本身的判据全在这里测。
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts/validate_deliverables.py"
SPEC = importlib.util.spec_from_file_location("deliverables", MODULE)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def fixture_brief(**overrides) -> dict:
    """最小合法 ProductionBrief。测试用合成对象，不依赖任何具体项目。"""
    data = {
        "schema_version": 1,
        "id": "sample-brief",
        "topic_id": "T-01",
        "title": "样例",
        "status": "blocked",
        "objective": "样例",
        "audience": "样例",
        "formats": ["video"],
        "core_thesis": "样例",
        "fact_refs": ["sample-fact"],
        "script": [{"id": "s1", "spoken": "样例", "status": "draft"}],
        "required_assets": [{"id": "a1", "type": "image", "status": "missing"}],
        "prohibited_claims": [],
        "acceptance_criteria": ["样例"],
        "handoff": {"ready": False},
    }
    data.update(overrides)
    return data


class DeliverableContractTest(unittest.TestCase):
    def write_temp(self, data: dict) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False)
        json.dump(data, handle, ensure_ascii=False)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_fixture_brief_is_structurally_valid(self):
        self.assertEqual(VALIDATOR.validate(self.write_temp(fixture_brief())), [])

    def test_ready_handoff_cannot_hide_missing_assets(self):
        data = fixture_brief()
        data["handoff"]["ready"] = True
        errors = VALIDATOR.validate(self.write_temp(data))
        self.assertTrue(any("handoff ready" in error for error in errors))

    def test_ready_status_cannot_hide_blocked_script(self):
        data = fixture_brief(status="ready_for_production",
                             script=[{"id": "s1", "spoken": "", "status": "blocked"}])
        errors = VALIDATOR.validate(self.write_temp(data))
        self.assertTrue(any("blocked script" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
