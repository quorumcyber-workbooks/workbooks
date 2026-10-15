import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://prices.azure.com/api/retail/prices"

# These values must match the Cost Currency dropdown in the workbook.
CURRENCIES = [
    "GBP",
    "USD",
    "EUR",
    "CAD",
    "AUD",
]

# The Azure Retail Prices API supports filtering by service family. Data Lake
# records are narrowed further below because Storage contains other products.
PRICING_QUERIES = [
    ("Sentinel", "serviceName eq 'Sentinel'"),
]

DATA_LAKE_TERMS = (
    "data lake",
    "hierarchical namespace",
)


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
            response_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            if error.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"Azure Retail Prices API returned HTTP "
                    f"{error.code}: {response_body}"
                ) from error

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

        except URLError as error:
            if attempt == 4:
                raise RuntimeError(
                    f"Unable to connect to Azure Retail Prices API: "
                    f"{error}"
                ) from error

            delay = 10
            print(
                f"Network error; retrying in {delay} seconds "
                f"(attempt {attempt + 1}/5)"
            )
            time.sleep(delay)

    raise RuntimeError(
        f"Unable to retrieve pricing after five attempts: {url}"
    )


def is_data_lake_record(item):
    searchable_text = " ".join(
        str(item.get(field) or "")
        for field in ("productName", "skuName", "meterName")
    ).lower()

    return any(term in searchable_text for term in DATA_LAKE_TERMS)


def include_record(item, currency, pricing_category):
    if item.get("currencyCode") != currency:
        return False

    if pricing_category == "Sentinel":
        return item.get("serviceName") == "Sentinel"

    if pricing_category == "DataLake":
        return is_data_lake_record(item)

    return False


def normalise_record(item, pricing_category):
    return {
        "pricingCategory": pricing_category,
        "currencyCode": item.get("currencyCode"),
        "armRegionName": item.get("armRegionName"),
        "location": item.get("location"),
        "productName": item.get("productName"),
        "serviceName": item.get("serviceName"),
        "serviceFamily": item.get("serviceFamily"),
        "skuName": item.get("skuName"),
        "meterName": item.get("meterName"),
        "unitOfMeasure": item.get("unitOfMeasure"),
        "unitPrice": item.get("unitPrice"),
        "retailPrice": item.get("retailPrice"),
        "type": item.get("type"),
        "effectiveStartDate": item.get("effectiveStartDate"),
        "meterId": item.get("meterId"),
    }


def fetch_currency(currency, pricing_category, api_filter):
    query = urlencode(
        {
            "currencyCode": f"'{currency}'",
            "$filter": api_filter,
        }
    )

    next_url = f"{API_BASE}?{query}"
    records = []

    while next_url:
        payload = get_json(next_url)

        for item in payload.get("Items", []):
            if include_record(item, currency, pricing_category):
                records.append(
                    normalise_record(item, pricing_category)
                )

        next_url = (
            payload.get("NextPageLink")
            or payload.get("nextPageLink")
        )

    return records


def record_key(record):
    return (
        record.get("pricingCategory"),
        record.get("currencyCode"),
        record.get("armRegionName"),
        record.get("productName"),
        record.get("serviceName"),
        record.get("skuName"),
        record.get("meterName"),
        record.get("unitPrice"),
        record.get("effectiveStartDate"),
        record.get("type"),
    )


def main():
    all_records = []

    for currency in CURRENCIES:
        for pricing_category, api_filter in PRICING_QUERIES:
            print(
                f"Fetching {pricing_category} prices for {currency}"
            )

            all_records.extend(
                fetch_currency(
                    currency,
                    pricing_category,
                    api_filter,
                )
            )

    unique_records = {
        record_key(record): record
        for record in all_records
    }

    prices = sorted(
        unique_records.values(),
        key=lambda item: (
            item.get("pricingCategory") or "",
            item.get("currencyCode") or "",
            item.get("armRegionName") or "",
            item.get("productName") or "",
            item.get("skuName") or "",
            item.get("meterName") or "",
        ),
    )

    category_counts = Counter(
        item.get("pricingCategory")
        for item in prices
    )

    output = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "productName": "Sentinel and Data Lake",
        "pricingCategories": [
            "Sentinel",
            "DataLake",
        ],
        "currencies": CURRENCIES,
        "regions": sorted(
            {
                item["armRegionName"]
                for item in prices
                if item.get("armRegionName")
            }
        ),
        "recordCount": len(prices),
        "recordCounts": dict(sorted(category_counts.items())),
        "prices": prices,
    }

    output_path = Path("data/sentinel-prices.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(output, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {len(prices)} pricing records across "
        f"{len(CURRENCIES)} currencies and "
        f"{len(output['regions'])} regions"
    )

    for category in ("Sentinel", "DataLake"):
        print(
            f"{category} records: "
            f"{category_counts.get(category, 0)}"
        )

        if category_counts.get(category, 0) == 0:
            print(
                f"WARNING: no {category} records were found. "
                "Check the Azure meter names before replacing "
                "the workbook's manual parameters."
            )


if __name__ == "__main__":
    main()
