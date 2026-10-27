"""Exercise rendered references and timed offers without a browser dependency."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent

class InterfaceTests(unittest.TestCase):
    def test_reference_links_and_start_times(self):
        script = (ROOT/'index.html').read_text().split('<script>')[1].split('</script>')[0].split('async function load(){')[0]
        registry = json.loads((ROOT/'stores.json').read_text())['stores']
        # Fixed test-only fixtures survive scheduled removal of expired offers.
        offers = [dict(store_id='yamakishi', vegetable_id=v, price_yen=1, unit='テスト専用', tax_included=True, valid_from=start, valid_until=end, verified_at='2026-10-27T00:00:00+09:00', source_url='https://example.org/test', verification_method='manual_source_review', evidence_text='テスト専用', conditions='テスト専用', **extra) for v,start,end,extra in [('cabbage','2026-10-27','2026-10-27',{'valid_from_time':'15:00'}),('carrot','2026-10-29','2026-10-29',{})]]
        js = "global.localStorage={getItem:()=>null};\n" + script + '\n'
        js += 'stores='+json.dumps(registry, ensure_ascii=False)+';prices=[];\n'
        js += '''
const assert=require('node:assert/strict');
assert.equal(safeSourceUrl('javascript:alert(1)'),null);
assert.equal(safeSourceUrl('https://user:secret@example.org'),null);
assert.equal(safeSourceUrl('http://example.org'),null);
const page=renderSources();
for(const s of stores){
  assert.ok(page.includes(esc(s.name)),s.id);
  for(const link of s.reference_links)assert.ok(page.includes(esc(safeSourceUrl(link.url))),link.url);
}
assert.ok(sourceCard(stores.find(s=>s.id==='yamakishi')).includes('公式チラシ'));
assert.ok(sourceCard(stores.find(s=>s.id==='yamakishi')).includes('価格未確認'));
collectionStatus={status:'candidates_ready',image_count:2,candidate_count:3,checked_at:'2026-10-27T00:00:00+09:00'};
assert.ok(sourceCard(stores.find(s=>s.id==='yamakishi')).includes('未確認・価格には未反映'));
assert.ok(!sourceCard(stores.find(s=>s.id==='aeon')).includes('野菜名の候補'));
assert.ok(!sourceLinks({reference_links:[{label:'unsafe',url:'javascript:alert(1)'}]}).includes('href='));
'''
        js += 'const offers='+json.dumps(offers, ensure_ascii=False)+';\n'
        js += '''
const OriginalDate=Date;
let clock='2026-10-27T14:59:00+09:00';
global.Date=class extends OriginalDate{constructor(...args){super(...(args.length?args:[clock]));}};
const cabbage={...offers.find(p=>p.store_id==='yamakishi'&&p.vegetable_id==='cabbage'),verified_at:'2026-10-27T00:00:00+09:00'};
assert.equal(valid(cabbage),false);
clock='2026-10-27T15:00:00+09:00';assert.equal(valid(cabbage),true);
clock='2026-10-28T00:00:00+09:00';assert.equal(valid(cabbage),false);
const carrot={...offers.find(p=>p.store_id==='yamakishi'&&p.vegetable_id==='carrot'),verified_at:'2026-10-27T00:00:00+09:00'};
assert.equal(valid(carrot),false);
clock='2026-10-29T09:00:00+09:00';assert.equal(valid(carrot),true);
'''
        subprocess.run(['node','-e',js],check=True,capture_output=True,text=True)
