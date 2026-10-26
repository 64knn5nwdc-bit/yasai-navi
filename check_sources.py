"""Check official flyer pages without inventing prices."""

from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import os

SOURCES = {
    "イオン松任店": (
        "https://www.aeon.com/store/"
        "%E3%82%A4%E3%82%AA%E3%83%B3/"
        "%E3%82%A4%E3%82%AA%E3%83%B3"
        "%E6%9D%BE%E4%BB%BB%E5%BA%97/"
    )
}

def main():
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    lines = [
        "# 野菜最安ナビ｜情報源チェック",
        f"確認日時：{now:%Y-%m-%d %H:%M} JST",
        "",
    ]

    for name, url in SOURCES.items():
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "YasaiNaviSourceCheck/1.0"
                },
            )
            with urlopen(request, timeout=20) as response:
                content = response.read(500000).decode(
                    "utf-8", errors="replace"
                )
                status = response.status

            if status == 200 and "チラシ情報" in content:
                result = "公式ページに接続成功"
            else:
                result = "内容を確認できませんでした"

        except (URLError, HTTPError, TimeoutError) as error:
            result = f"接続失敗：{type(error).__name__}"

        lines.append(f"## {name}")
        lines.append(f"- 状態：{result}")
        lines.append(f"- URL：{url}")
        lines.append("- 野菜価格：未取得")
        lines.append("")

    report = "\n".join(lines)
    print(report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as file:
            file.write(report + "\n")

if __name__ == "__main__":
    main()
