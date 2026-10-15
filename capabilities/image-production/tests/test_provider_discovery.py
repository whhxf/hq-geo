import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts/discover_provider.py'
SPEC = importlib.util.spec_from_file_location('discover_provider', PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class DiscoveryTests(unittest.TestCase):
    def test_actual_host_tool_wins(self):
        result = MOD.discover([{'id': 'native', 'available': True, 'operations': ['generate']}])
        self.assertEqual(result['provider'], 'native')

    def test_name_alone_does_not_claim_capability(self):
        self.assertEqual(MOD.discover([{'id': 'image_gen'}])['status'], 'needs_user_input')

    def test_local_skill_needs_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'SKILL.md'
            path.write_text('test')
            item = {'id': 'local', 'path': str(path)}
            self.assertEqual(MOD.discover([], [item])['status'], 'needs_user_input')
            item['executable_verified'] = True
            self.assertEqual(MOD.discover([], [item])['provider'], 'local')

    def test_missing_everything_asks_user(self):
        self.assertEqual(MOD.discover([])['status'], 'needs_user_input')
