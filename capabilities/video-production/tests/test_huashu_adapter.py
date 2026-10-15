import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts/huashu_adapter.py'
SPEC = importlib.util.spec_from_file_location('huashu_adapter', PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class AdapterTests(unittest.TestCase):
    def test_integrated_entry_not_external_vendor(self):
        self.assertTrue(MOD.ENGINE.is_file())
        self.assertNotIn('hq-vendor', str(MOD.ENGINE))

    def test_explicit_route_and_unsupported_style(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = Path(temp) / 'clip.json'
            spec.write_text(json.dumps({'grammar': 'y2_vox', 'duration': 4}))
            cmd = MOD.command(spec, Path(temp) / 'out.mp4')
            self.assertIn(str(MOD.ENGINE), cmd)
            spec.write_text(json.dumps({'grammar': 'invented', 'duration': 4}))
            with self.assertRaises(ValueError):
                MOD.command(spec, Path(temp) / 'out.mp4')
