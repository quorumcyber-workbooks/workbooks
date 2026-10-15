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
    ("DataLake", "serviceFamily eq 'Storage'"),
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
