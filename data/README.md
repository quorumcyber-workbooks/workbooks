# Microsoft Sentinel pricing data

`data/sentinel-prices.json` is the generated retail-pricing snapshot used by the Microsoft Sentinel workbook: Customer Info from v1.5.2 onwards

The workbook uses this file to look up Sentinel PAYG and Commitment Tier prices by:

- Currency
- Azure region
- Sentinel SKU
- Effective price date

Source file: [`data/sentinel-prices.json`](https://github.com/quorumcyber-workbooks/workbooks/blob/main/data/sentinel-prices.json)

## Data source

The file is generated from the Azure Retail Prices API and filtered to Microsoft Sentinel pricing.

It contains Microsoft retail prices only. Customer-specific agreements, partner discounts, credits, tax, and other commercial adjustments are not included.

Supported workbook currencies:

- GBP
- USD
- EUR
- CAD
- AUD

Unsupported currencies should not be added unless the pricing generator and workbook filtering logic are updated together.

## File structure

The generated document contains metadata and a collection of price records.

| Field | Description |
|---|---|
| `generatedAtUtc` | UTC timestamp when the snapshot was generated. |
| `productName` | Product represented by the snapshot. |
| `currencies` | Currencies included in the dataset. |
| `regions` | Azure regions represented in the dataset. |
| `recordCount` | Number of price records in the snapshot. |
| `prices` | Array of Sentinel retail price records. |

Price records include fields such as:

| Field | Description |
|---|---|
| `currencyCode` | Retail price currency. |
| `armRegionName` | Azure region code used by the workbook. |
| `location` | Azure region display name. |
| `serviceName` | Azure service name; expected to be `Sentinel`. |
| `skuName` | Sentinel SKU or Commitment Tier name. |
| `meterName` | Azure billing meter name. |
| `unitOfMeasure` | Billing unit returned by the pricing API. |
| `unitPrice` | Current retail unit price used by the workbook. |
| `retailPrice` | Retail price returned by the API. |
| `type` | Price type returned by the API. |
| `effectiveStartDate` | Date from which the price is effective. |
| `meterId` | Azure meter identifier. |

## Workbook usage

The workbook loads the JSON with KQL `externaldata`, expands the `prices` array, and filters the results using the selected currency, workspace region, and SKU.

The lookup contract is equivalent to:

```kusto
| where ServiceName =~ "Sentinel"
| where CurrencyCode == '{currencyCode}'
| where Region == '{armRegionName}'
| where SkuName == '{sentinelSkuNameFull}'
