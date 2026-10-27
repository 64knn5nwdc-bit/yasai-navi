"""Fetch the two linked food-flyer images and produce UNVERIFIED OCR hints.

Never imports collect_prices or writes prices.json. Images and full OCR output
exist only in a temporary directory and are not committed or uploaded.
"""
import argparse
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlsplit
from source_access import SourceClient, AccessStopped

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://yamakishi.co.jp/news/kawakita'
NAMES = {'negi': ('白ねぎ', '長ねぎ'), 'cabbage': ('キャベツ',), 'onion': ('玉ねぎ', 'たまねぎ'),
         'carrot': ('にんじん', '人参'), 'potato': ('じゃがいも',),
         'daikon': ('大根', 'だいこん'), 'tomato': ('トマト',),
         'cucumber': ('きゅうり',), 'hakusai': ('白菜',),
         'komatsuna': ('小松菜',), 'spinach': ('ほうれん草',)}

class FlyerLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.heading = ''
        self.in_heading = False
        self.links = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'h2':
            self.heading = ''
            self.in_heading = True
        if tag == 'a' and '川北店のチラシ' in self.heading and '有効期限' in self.heading:
            url = urljoin(SOURCE, d.get('href', ''))
            path = urlsplit(url).path
            if urlsplit(url).hostname == 'yamakishi.co.jp' and re.fullmatch(r'/news/wp-content/uploads/\d{4}/\d{2}/\d{4}_(?:kawakita_omote|shoku_ura)\.jpg', path):
                pair = (self.heading.strip(), url)
                if pair not in self.links:
                    self.links.append(pair)
    def handle_data(self, data):
        if self.in_heading:
            self.heading += data
    def handle_endtag(self, tag):
        if tag == 'h2':
            self.in_heading = False

def flyer_period(title, url):
    # Metadata only. NEVER copied into a product's valid_from / valid_until.
    ds = re.findall(r'(\d{1,2})/(\d{1,2})', title)
    upload = re.search(r'/uploads/(\d{4})/(\d{2})/(\d{2})(\d{2})_', url)
    if len(ds) != 2 or not upload:
        raise ValueError('flyer_period_requires_review')
    year = int(upload[1])
    start = date(year, *map(int, ds[0]))
    end = date(year + (int(ds[1][0]) < start.month), *map(int, ds[1]))
    if (start.month, start.day) != (int(upload[3]), int(upload[4])) or not 0 <= (end-start).days <= 31:
        raise ValueError('flyer_period_inconsistent')
    return {'start': start.isoformat(), 'end': end.isoformat(), 'kind': 'flyer_metadata_not_product_sale_dates'}

def ocr_lines(tsv):
    groups = {}
    for r in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
        if r.get('level') != '5' or not r.get('text', '').strip():
            continue
        try:
            box = [int(r[k]) for k in ('left', 'top', 'width', 'height')]
            confidence = float(r['conf'])
        except (TypeError, ValueError, KeyError):
            continue
        if not math.isfinite(confidence) or confidence < 0 or any(n < 0 for n in box) or not all(box[2:]):
            continue
        key = tuple(r.get(k) for k in ('page_num', 'block_num', 'par_num', 'line_num'))
        groups.setdefault(key, []).append((box, confidence, r['text']))
    result = []
    for words in groups.values():
        words.sort(key=lambda w: w[0][0])
        left = min(w[0][0] for w in words)
        top = min(w[0][1] for w in words)
        right = max(w[0][0]+w[0][2] for w in words)
        bottom = max(w[0][1]+w[0][3] for w in words)
        result.append({'text': ''.join(w[2] for w in words)[:180], 'bbox': [left, top, right-left, bottom-top],
                       'confidence': round(min(w[1] for w in words), 2)})
    return result

def ocr_page_size(tsv):
    """Read original-image dimensions from Tesseract's page row, without crops."""
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
        if row.get('level') == '1':
            try:
                width, height = int(row['width']), int(row['height'])
                if 0 < width <= 10000 and 0 < height <= 10000 and width * height <= 25_000_000:
                    return width, height
            except (KeyError, TypeError, ValueError):
                pass
            break
    raise ValueError('ocr_image_dimensions_require_review')

def one_character_apart(a, b):
    if a == b or abs(len(a)-len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    return any(a == b[:i]+b[i+1:] for i in range(len(b)))

def name_matches(text):
    text = ''.join(unicodedata.normalize('NFKC', text).split())
    exact = [v for v, aliases in NAMES.items() if any(a in text for a in aliases)]
    if exact:
        return [(v, 'exact_text') for v in exact]
    # A near match is only a review suggestion, NEVER a corrected OCR fact.
    # Short names and long mixed-product lines are too ambiguous to suggest.
    near = [v for v, aliases in NAMES.items() if len(text) <= 6 and any(len(a) >= 4 and one_character_apart(text, a) for a in aliases)]
    return [(near[0], 'one_character_difference')] if len(near) == 1 else []

def candidates(lines, image_url, digest, mode):
    results = []
    for line in lines:
        for vegetable, match_method in name_matches(line['text']):
            x, y, width, height = line['bbox']
            # Do not concatenate unrelated prices from nearby columns.
            text = line['text'][:180]
            key = image_url + digest + vegetable + json.dumps(line['bbox']) + str(mode)
            results.append({'id': hashlib.sha256(key.encode()).hexdigest()[:24], 'store_id': 'yamakishi',
                            'vegetable_hint': vegetable, 'source_url': image_url, 'image_sha256': digest,
                            'ocr_mode': mode, 'bbox': line['bbox'], 'ocr_confidence': line['confidence'],
                            'match_method': match_method,
                            'evidence_hint': text, 'review_status': 'unverified',
                            'price_yen': None, 'unit': None, 'valid_from': None, 'valid_until': None,
                            'review_required': ['product_price_association', 'tax_included_price', 'quantity_unit', 'product_sale_dates_and_times', 'purchase_conditions']})
    return results[:30]

def run_ocr(path, tessdata=None):
    args = ['tesseract', str(path), 'stdout', '-l', 'jpn', '--psm', '11', '-c', 'tessedit_create_tsv=1']
    if tessdata:
        args += ['--tessdata-dir', str(tessdata)]
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=60).stdout

def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temp.replace(path)

def extract_image(file, url, period, tessdata=None):
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    tsv = run_ocr(file, tessdata)
    width, height = ocr_page_size(tsv)
    found = candidates(ocr_lines(tsv), url, digest, 11)
    return ({'source_url': url, 'sha256': digest, 'width': width, 'height': height,
             'flyer_period': period, 'ocr_product_hints': len(found)}, found)

def collect(client, tessdata=None):
    body, kind, robots = client.get(SOURCE)
    parser = FlyerLinks()
    parser.feed(body.decode('utf-8', errors='strict'))
    if not parser.links:
        raise ValueError('flyer_links_require_review')
    today = datetime.now(ZoneInfo('Asia/Tokyo')).date()
    images, hints = [], []
    with tempfile.TemporaryDirectory(prefix='yasai-ocr-') as work:
        for title, url in parser.links[:2]:
            period = flyer_period(title, url)
            if date.fromisoformat(period['end']) < today:
                continue
            data, image_kind, _ = client.get(url, limit=12_000_000)
            if not data.startswith(b'\xff\xd8\xff'):
                raise ValueError('unexpected_image_format')
            file = Path(work) / 'flyer.jpg'
            file.write_bytes(data)
            image, found = extract_image(file, url, period, tessdata)
            images.append(image)
            hints.extend(found)
    return {'robots_status': robots, 'images': images, 'candidates': hints}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tessdata-dir')
    args = ap.parse_args()
    now = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
    status = {'checked_at': now, 'store_id': 'yamakishi', 'source_url': SOURCE,
              'publication_mode': 'candidate_only', 'auto_publish': False}
    try:
        if not shutil.which('tesseract'):
            raise ValueError('ocr_unavailable')
        result = collect(SourceClient(max_requests=5), args.tessdata_dir)
        status.update(status='candidates_ready' if result['images'] else 'no_current_flyer',
                      image_count=len(result['images']), candidate_count=len(result['candidates']), robots_status=result['robots_status'])
        atomic_json(ROOT/'review_candidates.json', {'schema_version': 2, 'last_success_at': now,
                    'warning': 'UNVERIFIED OCR HINTS. Never use as prices or product sale dates.', **result})
    except (AccessStopped, ValueError, OSError, subprocess.SubprocessError) as error:
        status.update(status='collection_stopped', reason=str(error)[:160] if isinstance(error, (AccessStopped, ValueError)) else type(error).__name__)
        # A failed attempt preserves the last successful candidates and its date.
    if not (ROOT/'review_candidates.json').exists():
        atomic_json(ROOT/'review_candidates.json', {'schema_version': 1, 'last_success_at': None, 'warning': 'UNVERIFIED OCR HINTS. Never use as prices.', 'images': [], 'candidates': []})
    atomic_json(ROOT/'collection_status.json', status)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    print('prices.json is unchanged: OCR hints require source review.')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write('## 未確認OCR候補（価格は自動公開しません）\n```json\n'+json.dumps(status, ensure_ascii=False, indent=2)+'\n```\n')

if __name__ == '__main__':
    main()
