import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parent

VEGETABLES = {
    "cabbage", "onion", "carrot", "potato",
    "daikon", "tomato", "cucumber",
    "hakusai", "komatsuna", "spinach"
}

def main():
    stores = {
        s["id"] for s in json.loads(
            (ROOT / "stores.json").read_text(encoding="utf-8")
        )["stores"]
    }

    path = ROOT / "prices.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    clean = []

    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()

    for p in obj.get("prices", []):
        try:
            assert p["vegetable_id"] in VEGETABLES
            assert p["store_id"] in stores
            assert type(p["price_yen"]) in (int, float)
            assert p["price_yen"] >= 0
            assert p["unit"].strip()
            assert p["source_url"].startswith("https://")

            datetime.fromisoformat(
                p["verified_at"].replace("Z", "+00:00")
            )

            end = datetime.strptime(
                p["valid_until"], "%Y-%m-%d"
            ).date()

            assert end >= today

            if p.get("valid_from"):
                start = datetime.strptime(
                    p["valid_from"], "%Y-%m-%d"
                ).date()
                assert start <= end

        except (
            KeyError, AssertionError, ValueError,
            TypeError, AttributeError
        ):
            continue

        clean.append(p)

    if clean != obj.get("prices", []):
        obj["prices"] = clean
        obj["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds")

        path.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )

    print(f"Validated {len(clean)} price records.")

if __name__ == "__main__":
    main()
