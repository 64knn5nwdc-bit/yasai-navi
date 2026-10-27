"""Validate evidence-backed records. No price inference or paid services."""
import json
import math
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
VEGETABLES = {'cabbage','onion','negi','carrot','potato','daikon','tomato','cucumber','hakusai','komatsuna','spinach'}

def valid_record(p, stores, now):
    try:
        if p['vegetable_id'] not in VEGETABLES or p['store_id'] not in stores:
            return False
        if type(p['price_yen']) not in (int, float) or not math.isfinite(p['price_yen']) or p['price_yen'] <= 0:
            return False
        if not isinstance(p['unit'], str) or not p['unit'].strip() or p.get('tax_included') is not True:
            return False
        u = urlsplit(p['source_url'])
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            return False
        start, end = date.fromisoformat(p['valid_from']), date.fromisoformat(p['valid_until'])
        if 'valid_from_time' in p:
            value = p['valid_from_time']
            if not isinstance(value, str) or len(value) != 5 or time.fromisoformat(value).isoformat(timespec='minutes') != value:
                return False
        checked = datetime.fromisoformat(p['verified_at'].replace('Z', '+00:00'))
        if checked.tzinfo is None or checked > now or start > end or end < now.date():
            return False
        # Explicit review is required: a timestamp or a URL alone is not evidence.
        if p.get('verification_method') != 'manual_source_review' or not p.get('evidence_text', '').strip():
            return False
        if not p.get('conditions', '').strip():
            return False
        return True
    except (KeyError, ValueError, TypeError, AttributeError):
        return False

def main():
    now = datetime.now(ZoneInfo('Asia/Tokyo'))
    stores = {s['id'] for s in json.loads((ROOT/'stores.json').read_text())['stores']}
    path = ROOT/'prices.json'
    obj = json.loads(path.read_text())
    clean = [p for p in obj.get('prices', []) if valid_record(p, stores, now)]
    if clean != obj.get('prices', []):
        obj.update(prices=clean, updated_at=now.isoformat(timespec='seconds'))
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        tmp.replace(path)
    print(f'Validated {len(clean)} records. New automatic price collection: disabled (source not approved).')

if __name__ == '__main__':
    main()
