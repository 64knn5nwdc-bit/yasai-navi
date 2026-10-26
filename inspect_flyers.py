from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from urllib.error import URLError, HTTPError

from urllib.parse import quote

URL = "https://www.aeon.com/store/" + quote("イオン/イオン松任店/")

class LinkFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            label = "".join(self.text).strip()
            link = urljoin(URL, self.href)
            if any(word in (label + link).lower()
                   for word in ["チラシ", "chirashi", "flyer"]):
                self.links.append((label, link))
            self.href = None
            self.text = []

try:
    req = Request(URL, headers={
        "User-Agent": "Mozilla/5.0"
    })
    with urlopen(req, timeout=20) as response:
        html = response.read(1000000).decode(
            "utf-8", errors="replace"
        )

    finder = LinkFinder()
    finder.feed(html)

    print("イオン松任店｜チラシリンク調査")
    print("検出数:", len(finder.links))

    for label, link in finder.links:
        print("名称:", label)
        print("URL:", link)

    if not finder.links:
        print("HTML内にチラシリンクは見つかりませんでした")

except (URLError, HTTPError, TimeoutError) as e:
    print("取得失敗:", type(e).__name__)
