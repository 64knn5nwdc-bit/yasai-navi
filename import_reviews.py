"""Validate reviewer drafts. Writing prices requires --apply and a source hash check.

No scheduled workflow calls this importer. A draft is not proof of accuracy;
the repository maintainer must personally review the official source first.
"""
import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from collect_candidates import atomic_json
from collect_prices import valid_record
from source_access import SourceClient, AccessStopped

ROOT = Path(__file__).resolve().parent
CHECKS = {'store_product','tax_included','quantity','sale_dates','conditions'}

def official_image(url):
    if not isinstance(url, str):
        return False
    p = urlsplit(url)
    return p.scheme == 'https' and p.netloc == 'yamakishi.co.jp' and not p.query and not p.fragment and bool(re.fullmatch(r'/news/wp-content/uploads/\d{4}/\d{2}/\d{4}_(kawakita_omote|shoku_ura)\.jpg', p.path))

def prepare(draft, manifest, existing, stores, now):
    if draft.get('schema_version') != 1 or draft.get('publication_status') != 'draft_not_published':
        raise ValueError('確認画面で作成した未公開の下書きが必要です。')
    records = draft.get('records')
    if not isinstance(records, list) or not 1 <= len(records) <= 30:
        raise ValueError('下書きは1〜30件で指定してください。')
    images = {i.get('source_url'): i for i in manifest.get('images', [])}
    hints = {c.get('id'): c for c in manifest.get('candidates', [])}
    result, duplicates = [], 0
    identity_fields = ('store_id','vegetable_id','source_url','price_yen','unit','valid_from','valid_until','valid_from_time')
    def identity(p):
        return tuple(p.get(k) for k in identity_fields)
    for p in records:
        if not isinstance(p, dict) or p.get('store_id') != 'yamakishi' or not valid_record(p, stores, now):
            raise ValueError('店舗・商品・税込価格・単位・日付・原文確認根拠を検証できません。')
        if not official_image(p['source_url']):
            raise ValueError('取得対象の公式チラシ画像が情報源に必要です。')
        checks = p.get('review_checks')
        if not isinstance(checks, dict) or not all(checks.get(k) is True for k in CHECKS):
            raise ValueError('原本の確認項目が揃っていません。')
        image, hint = images.get(p['source_url']), hints.get(p.get('review_candidate_id'))
        sha = p.get('source_image_sha256', '')
        if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha) or not image or not hint or image.get('sha256') != sha or hint.get('image_sha256') != sha or hint.get('source_url') != p['source_url'] or hint.get('store_id') != p['store_id']:
            raise ValueError('現在の候補と下書きの原本が一致しません。原本を再確認してください。')
        period = image.get('flyer_period', {})
        try:
            start, end = date.fromisoformat(period['start']), date.fromisoformat(period['end'])
            if not start <= date.fromisoformat(p['valid_from']) <= date.fromisoformat(p['valid_until']) <= end:
                raise ValueError('商品別販売日がチラシの掲載期間から外れています。')
        except (TypeError, KeyError) as error:
            raise ValueError('チラシの期間情報を検証できません。') from error
        # Validate every record before writing anything; preserve existing offers.
        if any(identity(p) == identity(old) for old in [*existing, *result]):
            duplicates += 1
        else:
            result.append(p.copy())
    return result, duplicates

def verify_sources(records, client):
    verified = set()
    for p in records:
        key = (p['source_url'], p['source_image_sha256'])
        if key in verified:
            continue
        data, _, _ = client.get(key[0], limit=12_000_000)
        if not data.startswith(b'\xff\xd8\xff') or hashlib.sha256(data).hexdigest() != key[1]:
            raise ValueError('公式画像が取得時から変わっています。公開せず原本を再確認してください。')
        verified.add(key)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('draft', type=Path)
    parser.add_argument('--apply', action='store_true', help='原本照合済みの下書きのみ価格データへ反映')
    args = parser.parse_args()
    try:
        draft = json.loads(args.draft.read_text(encoding='utf-8'))
        manifest = json.loads((ROOT/'review_candidates.json').read_text(encoding='utf-8'))
        obj = json.loads((ROOT/'prices.json').read_text(encoding='utf-8'))
        stores = {s['id'] for s in json.loads((ROOT/'stores.json').read_text(encoding='utf-8'))['stores']}
        now = datetime.now(ZoneInfo('Asia/Tokyo'))
        additions, duplicates = prepare(draft, manifest, obj['prices'], stores, now)
        if args.apply and additions:
            verify_sources(additions, SourceClient(max_requests=5))
            obj.update(prices=[*obj['prices'], *additions], updated_at=now.isoformat(timespec='seconds'))
            atomic_json(ROOT/'prices.json', obj)
        print(json.dumps({'mode': 'apply' if args.apply else 'dry_run', 'new_records': len(additions),
                          'duplicates_skipped': duplicates, 'prices_written': bool(args.apply and additions)}, ensure_ascii=False))
    except (AccessStopped, ValueError, OSError, TypeError, AttributeError, KeyError) as error:
        parser.error(str(error))

if __name__ == '__main__':
    main()
