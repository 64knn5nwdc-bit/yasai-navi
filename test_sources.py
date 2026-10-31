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
        self.assertEqual(len(sources), 6)
        self.assertNotIn('valor', sources)
        self.assertFalse(any(key.startswith('albis_') for key in sources))

    def test_policy_stores_are_reported_without_network(self):
        from unittest.mock import patch
        from check_sources import source_results
        with patch('check_sources.inspect', return_value={'status': 'test'}) as inspect_source:
            results = source_results()
        requested = {call.args[0] for call in inspect_source.call_args_list}
        skipped = [r for r in results if r['status'] == 'reference_only_policy']
        self.assertEqual({r['store_id'] for r in skipped}, {'valor', 'albis_kitayasuda', 'albis_terai', 'albis_tatsunokuchi'})
        for record in skipped:
            self.assertNotIn(record['url'], requested)
            self.assertEqual(record['price_collection'], 'disabled_pending_permission')
            self.assertTrue(record['policy_url'].startswith('https://'))
