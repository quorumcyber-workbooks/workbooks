import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://prices.azure.com/api/retail/prices"
API_VERSION = "2021-10-01"

CURRENCIES = [
    "USD",
    "AUD",
    "BRL",
    "GBP",
    "CAD",
    "CNY",
    "DKK",
    "EUR",
    "INR",
    "JPY",
    "KRW",
    "NZD",
    "NOK",
    "RUB",
    "SEK",
    "CHF",
    "TWD",
]

FILTER = "productName eq 'Sentinel'"


def get_json(url):
    for attempt in range(5):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "sentinel-pricing-data-github-action"
                },
            )

            with urlopen(request, timeout=90) as response:
                return json.load(response)

        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504):
                raise

            retry_after = error.headers.get("Retry-After", "10")

            try:
                delay = min(int(retry_after), 60)
            except ValueError:
                delay = 10

            print(
                f"HTTP {error.code}; retrying in {delay} seconds "
                f"(attempt {attempt + 1}/5)"
            )
            time.sleep(delay)

    raise RuntimeError(f"Unable to retrieve pricing after five attempts: {url}")


def fetch_currency(currency):
    query = urlencode(
        {
            "api-version": API_VERSION,
            "currencyCode": f"'{currency}'",
            "$filter": FILTER,
        }
    )

    next_url = f"{API_BASE}?{query}"
    records = []

    while next_url:
        payload = get_json(next_url)

        for item in payload.get("Items", []):
            if (
                item.get("productName") == "Sentinel"
                and item.get("currencyCode") == currency
            ):
                records.append(
                    {
                        "currencyCode": item.get("currencyCode"),
                        "armRegionName": item.get("armRegionName"),
                        "location": item.get("location"),
                        "productName": item.get("productName"),
                        "serviceName": item.get("serviceName"),
                        "skuName": item.get("skuName"),
                        "meterName": item.get("meterName"),
                        "unitOfMeasure": item.get("unitOfMeasure"),
                        "unitPrice": item.get("unitPrice"),
                        "retailPrice": item.get("retailPrice"),
                        "type": item.get("type"),
                        "effectiveStartDate": item.get(
                            "effectiveStartDate"
                        ),
                        "meterId": item.get("meterId"),
                    }
                )

        next_url = (
            payload.get("NextPageLink")
            or payload.get("nextPageLink")
        )

    return records


all_records = []

for currency in CURRENCIES:
    print(f"Fetching Sentinel prices for {currency}")
    all_records.extend(fetch_currency(currency))

# Remove accidental duplicates while preserving all regions/currencies.
unique_records = {}
for record in all_records:
    key = (
        record.get("currencyCode"),
        record.get("armRegionName"),
        record.get("skuName"),
        record.get("meterName"),
        record.get("unitPrice"),
        record.get("effectiveStartDate"),
        record.get("type"),
    )
    unique_records[key] = record

prices = sorted(
    unique_records.values(),
    key=lambda item: (
        item.get("currencyCode") or "",
        item.get("armRegionName") or "",
        item.get("skuName") or "",
        item.get("meterName") or "",
    ),
)

output = {
    "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
    "apiVersion": API_VERSION,
    "productName": "Sentinel",
    "currencies": CURRENCIES,
    "regions": sorted(
        {
            item["armRegionName"]
            for item in prices
            if item.get("armRegionName")
        }
    ),
    "recordCount": len(prices),
    "prices": prices,
}

output_path = Path("data/sentinel-prices.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

output_path.write_text(
    json.dumps(output, indent=2) + "\n",
    encoding="utf-8",
)

print(
    f"Wrote {len(prices)} Sentinel prices across "
    f"{len(CURRENCIES)} currencies and "
    f"{len(output['regions'])} regions"
)
