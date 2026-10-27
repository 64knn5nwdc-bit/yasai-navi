"""Test-only draft fixtures. No fixtures are used in published prices."""
from contextlib import redirect_stderr, redirect_stdout
import copy
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import import_reviews as importer

class ReviewImportTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.fromisoformat('2026-10-27T20:00:00+09:00')
        self.url='https://yamakishi.co.jp/news/wp-content/uploads/2026/10/1027_kawakita_omote.jpg'
        self.data=b'\xff\xd8\xffTEST ONLY'
        self.sha=hashlib.sha256(self.data).hexdigest()
        self.manifest={'images':[{'source_url':self.url,'sha256':self.sha,'flyer_period':{'start':'2026-10-27','end':'2026-10-29'}}], 'candidates':[{'id':'a'*24,'store_id':'yamakishi','source_url':self.url,'image_sha256':self.sha}]}
        self.record={'store_id':'yamakishi','vegetable_id':'cabbage','price_yen':100,'unit':'テスト専用1個','tax_included':True,'valid_from':'2026-10-27','valid_until':'2026-10-27','verified_at':self.now.isoformat(),'source_url':self.url,'verification_method':'manual_source_review','evidence_text':'テスト専用・公開価格には使用しない','conditions':'テスト専用','review_candidate_id':'a'*24,'source_image_sha256':self.sha,'review_checks':{k:True for k in importer.CHECKS}}
        self.draft={'schema_version':1,'publication_status':'draft_not_published','records':[self.record]}

    def prepare(self, draft=None, existing=None):
        return importer.prepare(draft or self.draft,self.manifest,existing or [],{'yamakishi'},self.now)

    def test_valid_draft_and_duplicate_preservation(self):
        additions, duplicates=self.prepare()
        self.assertEqual(additions,[self.record]);self.assertEqual(duplicates,0)
        self.assertEqual(self.prepare(existing=[self.record]),([],1))

    def test_missing_review_hash_and_invalid_dates_are_rejected(self):
        for key,value in [('review_checks',{}),('source_image_sha256','b'*64),('review_candidate_id','b'*24),('source_url','https://example.org/flyer.jpg'),('valid_until','2026-10-30'),('valid_from','2026-02-30'),('valid_from_time','25:00'),('price_yen',None)]:
            with self.subTest(key=key):
                draft=copy.deepcopy(self.draft);draft['records'][0][key]=value
                with self.assertRaises(ValueError):self.prepare(draft)

    def test_changed_original_image_is_rejected(self):
        client=Mock();client.get.return_value=(b'changed', 'image/jpeg', 'robots_absent_404')
        with self.assertRaises(ValueError):importer.verify_sources([self.record],client)
        client.get.assert_called_once()

    def test_batch_failure_does_not_partially_accept(self):
        draft=copy.deepcopy(self.draft);bad=self.record.copy();bad['unit']='';draft['records'].append(bad)
        with self.assertRaises(ValueError):self.prepare(draft)

    def test_cli_dry_run_and_atomic_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,obj in [('draft.json',self.draft),('prices.json',{'prices':[],'updated_at':None}),('review_candidates.json',self.manifest),('stores.json',{'stores':[{'id':'yamakishi'}]})]:
                (root/name).write_text(json.dumps(obj))
            original=(root/'prices.json').read_bytes()
            fake=Mock();fake.get.return_value=(self.data,'image/jpeg','robots_absent_404')
            with patch.object(importer,'ROOT',root),patch.object(importer,'datetime') as clock,patch.object(importer,'SourceClient',return_value=fake),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                clock.now.return_value=self.now
                with patch('sys.argv',['import_reviews.py',str(root/'draft.json')]):importer.main()
                self.assertEqual((root/'prices.json').read_bytes(),original);fake.get.assert_not_called()
                fake.get.return_value=(b'changed','image/jpeg','robots_absent_404')
                with patch('sys.argv',['import_reviews.py',str(root/'draft.json'),'--apply']),self.assertRaises(SystemExit):importer.main()
                self.assertEqual((root/'prices.json').read_bytes(),original)
                fake.get.return_value=(self.data,'image/jpeg','robots_absent_404')
                with patch('sys.argv',['import_reviews.py',str(root/'draft.json'),'--apply']):importer.main()
                self.assertEqual(json.loads((root/'prices.json').read_text())['prices'],[self.record])

class ReviewBrowserLogicTests(unittest.TestCase):
    def test_draft_validation_and_source_overlay(self):
        root=Path(__file__).resolve().parent
        js=r'''
const assert=require('node:assert/strict'), R=require('./review-core.js');
const url='https://yamakishi.co.jp/news/wp-content/uploads/2026/10/1027_kawakita_omote.jpg';
const c={id:'a'.repeat(24),store_id:'yamakishi',vegetable_hint:'cabbage',review_status:'unverified',source_url:url,image_sha256:'b'.repeat(64),bbox:[459,147,77,19]};
const image={source_url:url,sha256:c.image_sha256,width:2256,height:1606,flyer_period:{start:'2026-10-27',end:'2026-10-29'}};
const now=new Date('2026-10-27T20:00:00+09:00');
const fields={vegetable_id:'cabbage',price_yen:'100',unit:'テスト専用',valid_from:'2026-10-27',valid_until:'2026-10-27',valid_from_time:'15:00',conditions:'テスト専用',evidence_text:'テスト専用・公開には使用しない',checks:Object.fromEntries(R.checks.map(k=>[k,true]))};
assert.equal(R.usableCandidates({images:[image],candidates:[c]}).length,1);
assert.equal(R.sourceUrl('https://evil.example/a.jpg'),null);
assert.equal(R.sourceUrl('https://user:pass@yamakishi.co.jp/'+url.split('/').slice(3).join('/')),null);
assert.equal(R.usableCandidates({images:[image],candidates:[{...c,image_sha256:'c'.repeat(64)}]}).length,0);
assert.equal(R.focusBox(c,image).width,2256);
assert.equal(R.focusBox({...c,bbox:[3000,0,10,10]},image),null);
assert.equal(R.realDate('2026-02-30'),false);
const draft=R.makeDraft(c,image,fields,now);
assert.equal(draft.publication_status,'draft_not_published');
assert.equal(draft.records[0].tax_included,true);
assert.equal(draft.records[0].valid_from_time,'15:00');
for(const values of [{...fields,price_yen:''},{...fields,price_yen:'NaN'},{...fields,checks:{}},{...fields,valid_until:'2026-10-30'},{...fields,valid_from_time:'25:00'},{...fields,conditions:''}])assert.throws(()=>R.makeDraft(c,image,values,now));
assert.throws(()=>R.makeDraft(c,image,fields,new Date('2026-10-28T00:00:00+09:00')));
'''
        subprocess.run(['node','-e',js],cwd=root,check=True,capture_output=True,text=True)
