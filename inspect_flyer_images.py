
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import quote, urljoin

BASE = "https://www.aeon.com/store/"
URL = BASE + quote("イオン/イオン松任店/flyer/")

class ImageFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)

        if tag == "img":
            for key in ("src", "data-src", "data-original"):
                value = data.get(key)
                if value:
                    self.images.append(urljoin(URL, value))

        if tag == "a":
            value = data.get("href")
            if value:
                self.links.append(urljoin(URL, value))

req = Request(URL, headers={
    "User-Agent": "Mozilla/5.0"
})

with urlopen(req, timeout=20) as response:
    print("HTTP状態:", response.status)
    html = response.read(2000000).decode(
        "utf-8", errors="replace"
    )

finder = ImageFinder()
finder.feed(html)

print("\n=== 画像URL ===")
print("検出数:", len(set(finder.images)))

for image in sorted(set(finder.images)):
    print(image)

print("\n=== チラシ関連リンク ===")
for link in sorted(set(finder.links)):
    if any(word in link.lower() for word in (
        "flyer", "chirashi", "otoku", "pdf"
    )):
        print(link)

print("\n調査終了：価格データは変更していません")
