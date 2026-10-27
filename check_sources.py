"""Bounded, robots-aware diagnostics; never treats images as verified prices."""
import json
import os
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

UA = 'YasaiNaviSourceCheck/2.0'
SOURCES = {'aeon':'https://www.aeon.com/store/'+quote('イオン/イオン松任店/flyer/'), 'valor':'https://stores.valor.jp/detail/158/'}

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

def read(url):
    with urlopen(Request(url,headers={'User-Agent':UA}),timeout=15) as r:
        b=r.read(2_000_001)
        if len(b)>2_000_000: raise ValueError('Response too large')
        return b.decode('utf-8',errors='replace')

def inspect(url):
    origin='https://'+urlsplit(url).netloc
    try:
        robots=RobotFileParser(); robots.parse(read(origin+'/robots.txt').splitlines())
        if not robots.can_fetch(UA,url): return {'status':'robots_disallowed'}
    except Exception as e:
        return {'status':'robots_unavailable','error':type(e).__name__}
    try:
        html=read(url); parser=Structure(url); parser.feed(html)
        return {'status':'dynamic_source_requires_review' if parser.flyer_ids or parser.resources else 'requires_review','flyer_ids':sorted(set(parser.flyer_ids)),'resources':sorted(set(parser.resources)), 'viewer_urls':['https://chirashi.otoku.aeonsquare.net/pc/chirashi/otoku/com_frame.html?shop_id='+i for i in sorted(set(parser.flyer_ids))] if urlsplit(url).hostname=='www.aeon.com' else [],'price_collection':'disabled: permission and complete product evidence required'}
    except Exception as e:
        return {'status':'fetch_failed','error':type(e).__name__}

def main():
    obj={'checked_at':datetime.now().astimezone().isoformat(),'sources':[{ 'store_id':key,'url':url,**inspect(url)} for key,url in SOURCES.items()]}
    report=json.dumps(obj,ensure_ascii=False,indent=2)
    print(report)
    Path('source_status.json').write_text(report+'\n')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f: f.write('## 情報源診断（価格取得とは別）\n```json\n'+report+'\n```\n')
if __name__=='__main__': main()
