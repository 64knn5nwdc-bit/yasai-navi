"""Safe price-data validator. Does NOT scrape flyers or invent prices.

To add automated sources, implement a provider adapter that retrieves prices from
an officially permitted structured feed, retaining source URL, units and validity.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VEGETABLES = {'cabbage','onion','carrot','potato','daikon','tomato','cucumber','hakusai','komatsuna','spinach'}


def main():
    stores = {s['id'] for s in json.loads((ROOT/'stores.json').read_text(encoding='utf-8'))['stores']}
    path = ROOT/'prices.json'
    obj = json.loads(path.read_text(encoding='utf-8'))
    clean = []
    today = date.today()
    for p in obj.get('prices', []):
        try:
            assert p['vegetable_id'] in VEGETABLES
            assert p['store_id'] in stores
            assert type(p['price_yen']) in (int, float) and p['price_yen'] >= 0
            assert p['unit'].strip() and p['source_url'].startswith('https://')
            assert datetime.fromisoformat(p['verified_at'].replace('Z','+00:00'))
            assert date.fromisoformat(p['valid_until']) >= today
            if p.get('valid_from'):
                assert date.fromisoformat(p['valid_from']) <= today
        except (KeyError, AssertionError, ValueError, TypeError, AttributeError):
            continue
        clean.append(p)
    if clean != obj.get('prices', []):
        obj['prices'] = clean
        obj['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Validated {len(clean)} current price records. No source collector is configured yet.')

if __name__ == '__main__':
    main()
