"""Bounded, robots-aware diagnostics; never treats images as verified prices."""
import json
import os
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent

def load_sources():
    stores = json.loads((ROOT / 'stores.json').read_text(encoding='utf-8'))['stores']
    return {s['id']: s['flyer_url'] for s in stores if s.get('collection_policy') != 'reference_only' and s.get('source_check_enabled') is True and s.get('kind') == 'store' and s.get('flyer_url', '').startswith('https://')}


class Structure(HTMLParser):
    def __init__(self, base):
        super().__init__(); self.base=base; self.resources=[]; self.flyer_ids=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if d.get('data-flyer-id'): self.flyer_ids.append(d['data-flyer-id'])
        if tag in ('script','iframe') and d.get('src'):
            u=urljoin(self.base,d['src'])
            if any(s in u for s in ('aeon-store.js','shufoo','chirashi','flyer')):
                self.resources.append(u)

def inspect(url, client=None):
    from source_access import SourceClient, AccessStopped
    client = client or SourceClient(max_requests=3)
    try:
        body, kind, robots_status = client.get(url)
        html = body.decode('utf-8', errors='replace')
        parser = Structure(url)
        parser.feed(html)
        return {'status': 'dynamic_source_requires_review' if parser.flyer_ids or parser.resources else 'requires_review',
                'robots_status': robots_status, 'flyer_ids': sorted(set(parser.flyer_ids)),
                'resources': sorted(set(parser.resources)),
                'viewer_urls': ['https://chirashi.otoku.aeonsquare.net/pc/chirashi/otoku/com_frame.html?shop_id='+i for i in sorted(set(parser.flyer_ids))] if urlsplit(url).hostname=='www.aeon.com' else [],
                'price_collection': 'disabled: complete product evidence required'}
    except (AccessStopped, OSError, TimeoutError) as error:
        return {'status': 'fetch_stopped', 'reason': str(error) if isinstance(error, AccessStopped) else type(error).__name__}

def source_results():
    stores = json.loads((ROOT / 'stores.json').read_text(encoding='utf-8'))['stores']
    results = [{'store_id': key, 'url': url, **inspect(url)} for key, url in load_sources().items()]
    for store in stores:
        if store.get('kind') == 'store' and store.get('collection_policy') == 'reference_only':
            results.append({'store_id': store['id'], 'url': store['flyer_url'],
                            'status': 'reference_only_policy', 'policy_url': store['policy_url'],
                            'reason': store['collection_note'], 'price_collection': 'disabled_pending_permission'})
    return results


def main():
    obj={'checked_at':datetime.now().astimezone().isoformat(),'sources':source_results()}
    report=json.dumps(obj,ensure_ascii=False,indent=2)
    print(report)
    Path('source_status.json').write_text(report+'\n')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f: f.write('## 情報源診断（価格取得とは別）\n```json\n'+report+'\n```\n')
if __name__=='__main__': main()
