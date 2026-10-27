import unittest
from check_sources import Structure

class StructureTests(unittest.TestCase):
    def test_dynamic_placeholder(self):
        p=Structure("https://www.aeon.com/store/")
        p.feed('<div style="display:none">ただいまチラシの掲載はございません。</div><div data-flyer-id="0000025310"></div><script src="/store/pc/js/aeon-store.js"></script>')
        self.assertEqual(p.flyer_ids, ["0000025310"])
        self.assertEqual(p.resources, ["https://www.aeon.com/store/pc/js/aeon-store.js"])

class RegistryTests(unittest.TestCase):
    def test_only_verified_store_sources_are_checked(self):
        from check_sources import load_sources
        sources = load_sources()
        self.assertIn('yamakishi', sources)
        self.assertIn('acoop', sources)
        self.assertNotIn('genky', sources)
        self.assertNotIn('aoki', sources)
        self.assertEqual(len(sources), 7)
