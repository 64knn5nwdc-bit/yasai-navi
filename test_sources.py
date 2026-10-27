import unittest
from check_sources import Structure

class StructureTests(unittest.TestCase):
    def test_dynamic_placeholder(self):
        p=Structure("https://www.aeon.com/store/")
        p.feed('<div style="display:none">ただいまチラシの掲載はございません。</div><div data-flyer-id="0000025310"></div><script src="/store/pc/js/aeon-store.js"></script>')
        self.assertEqual(p.flyer_ids, ["0000025310"])
        self.assertEqual(p.resources, ["https://www.aeon.com/store/pc/js/aeon-store.js"])
