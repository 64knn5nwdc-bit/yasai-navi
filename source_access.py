"""Bounded public-source access. No retries, authentication or host hopping."""
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

UA = 'YasaiNaviSourceCheck/3.0 (+https://64knn5nwdc-bit.github.io/yasai-navi/)'

class AccessStopped(Exception):
    pass

def normalized_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise AccessStopped('invalid_source_url')
    return quote(url, safe=":/?&=%+;,@!$'()*-._~")

class SameHostRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        # Observed official robots redirect; applies only to this exact robots URL.
        robots_alias = req.full_url == 'https://yamakishi.co.jp/robots.txt' and newurl == 'https://www.yamakishi.co.jp/robots.txt'
        if (new.hostname != old.hostname and not robots_alias) or new.scheme != 'https':
            raise AccessStopped('redirect_requires_review')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class SourceClient:
    def __init__(self, max_requests=12):
        self.opener = build_opener(SameHostRedirects())
        self.max_requests = max_requests
        self.requests = 0
        self.rules = {}
        self.last_request = {}

    def raw(self, url, limit):
        url = normalized_url(url)
        if self.requests >= self.max_requests:
            raise AccessStopped('request_budget_exhausted')
        self.requests += 1
        with self.opener.open(Request(url, headers={'User-Agent': UA}), timeout=12) as response:
            body = response.read(limit + 1)
            if len(body) > limit:
                raise AccessStopped('response_too_large')
            return body, response.headers.get('Content-Type', '')

    def permission(self, url):
        p = urlsplit(normalized_url(url))
        origin = p.scheme + '://' + p.netloc
        if origin not in self.rules:
            try:
                body, kind = self.raw(origin + '/robots.txt', 512 * 1024)
                if '<html' in body[:500].decode('utf-8', errors='ignore').lower():
                    raise AccessStopped('robots_invalid_content')
                rules = RobotFileParser()
                rules.parse(body.decode('utf-8', errors='replace').splitlines())
                self.rules[origin] = ('robots_available', rules)
            except HTTPError as error:
                # RFC 9309 permits access for unavailable robots. Be stricter for
                # authentication, rate limits and all other unexpected failures.
                if error.code in (404, 410):
                    self.rules[origin] = ('robots_absent_' + str(error.code), None)
                else:
                    raise AccessStopped('robots_http_' + str(error.code)) from error
            except AccessStopped:
                raise
            except (OSError, TimeoutError) as error:
                raise AccessStopped('robots_unreachable') from error
        status, rules = self.rules[origin]
        if rules and not rules.can_fetch('YasaiNaviSourceCheck', normalized_url(url)):
            raise AccessStopped('robots_disallowed')
        delay = rules.crawl_delay('YasaiNaviSourceCheck') if rules else None
        if delay is not None and delay > 10:
            raise AccessStopped('crawl_delay_requires_review')
        return origin, status, max(1, delay or 0)

    def get(self, url, limit=2_000_000):
        origin, status, delay = self.permission(url)
        remaining = delay - (time.monotonic() - self.last_request.get(origin, 0))
        if remaining > 0:
            time.sleep(remaining)
        self.last_request[origin] = time.monotonic()
        try:
            body, kind = self.raw(url, limit)
        except HTTPError as error:
            raise AccessStopped('source_http_' + str(error.code)) from error
        return body, kind, status
