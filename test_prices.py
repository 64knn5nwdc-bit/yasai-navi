import unittest
from datetime import datetime
from collect_prices import valid_record

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat('2026-10-26T23:00:00+09:00')
        self.p = dict(vegetable_id='onion',store_id='aeon',price_yen=100,unit='1個',tax_included=True,valid_from='2026-10-26',valid_until='2026-10-27',verified_at='2026-10-26T22:00:00+09:00',source_url='https://example.org/flyer',verification_method='manual_source_review',evidence_text='テスト用の架空レコード。公開データには使用しない',conditions='条件なし')
    def test_valid(self):
        self.assertTrue(valid_record(self.p, {'aeon'}, self.now))
    def test_reject_unsafe_or_incomplete(self):
        for key, value in [('price_yen',float('nan')),('price_yen',float('inf')),('price_yen',True),('price_yen',-1),('tax_included',False),('source_url','javascript:alert(1)'),('verified_at','2026-10-26T22:00:00'),('verified_at','2026-10-27T22:00:00+09:00'),('valid_until','2026-10-25'),('valid_from','2026-10-28'),('evidence_text',''),('conditions',''),('store_id','unknown')]:
            with self.subTest(key=key,value=value):
                self.assertFalse(valid_record(dict(self.p, **{key:value}), {'aeon'}, self.now))
    def test_missing_fields(self):
        for key in self.p:
            p=self.p.copy(); del p[key]
            self.assertFalse(valid_record(p, {'aeon'}, self.now), key)

if __name__ == '__main__': unittest.main()
