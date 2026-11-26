# Source contract and KPI dictionary (v1)

## File contract

UTF-8 CSV (optional UTF-8 BOM), exact column order, one source sale line per row. The loader strips outer whitespace, checks field lengths, rejects malformed rows, and rejects repeated IDs in one file. Maximum 20 MB and 100,000 rows; empty batches are invalid. IDs are case-sensitive within one dedicated warehouse/source namespace (ASCII letters/digits plus underscore, hyphen, period, colon; 1–64 characters). A production multi-source adapter must namespace IDs by source.

```csv
sale_id,sold_on,product_id,product_type,category,material,customer_id,city,region,state,country,quantity,gross_cents,discount_cents,currency
SALE-001,2025-05-01,P-001,Sofa,Living Room,Fabric,C-001,Toronto,Central,Ontario,Canada,2,100000,5000,USD
```

| Field group | Meaning / validation |
|---|---|
| sale_id | Stable immutable event ID; repeat only with identical normalized data |
| sold_on | Valid calendar date, YYYY-MM-DD, 2000–2100 |
| product_id, customer_id | Stable business identifiers, not real names |
| product_type, category, material | Nonempty sale-time product description (max 120 characters) |
| city, region, state, country | Nonempty sale-time geography (max 120 characters) |
| quantity | Integer 1–100,000 |
| gross_cents | Integer 0–10,000,000,000; gross **line** amount before discount |
| discount_cents | Integer 0–gross_cents |
| currency | Exactly USD for this single-currency demonstration |

No costs, tax, refund, full order ID, customer names, contact details, age or sex are required. Stop before import when the source semantics differ. The new synthetic generator is not based on actual client sales.

## Metrics

| KPI | Formula | Behavior |
|---|---|---|
| Sale lines | Count facts | Not order count |
| Units sold | Sum quantity | Product demand |
| Gross revenue | Sum gross_cents / 100 | Before discounts; USD |
| Total discounts | Sum discount_cents / 100 | USD |
| Net revenue | Sum (gross_cents − discount_cents) / 100 | USD; not profit |
| Distinct customers | Count distinct customer_id | Business key; not snapshot rows |
| Distinct products | Count distinct product_id | Business key |
| Repeat customers | Count customers with more than one sale line in selection | Not repeat orders or retention rate |
| Discount rate | Total discounts / gross revenue × 100 | Null when gross is 0 |
| Average sale | Net cents / sale line count, rounded to cents | Null when none |
| Monthly YoY | (current net − prior same calendar month net) / prior × 100 | Same selected filters; null when prior missing or zero |

All dashboard values reflect inclusive date filters plus selected category and country. YoY exists only if both calendar months occur in the selected window, and partial-month filters compare the included portions, not guaranteed full months. Whole-warehouse quality/run history/available filter options are not filtered. Dates with no observations are not invented. The dashboard rounds currency to whole dollars for display; JSON and exported CSV preserve exact cents. Top ten product types are limited to ten rows; equal quantity gets the same dense rank. Category list (top 100), region (top 20) and filter options (up to 250 each) are deliberately bounded.

## Legacy mapping

The original SQL sample contains 100 rows in each source table. `Income` and `Discount` are not independently defined as USD or gross-before-discount. The opt-in exporter requires `--assume-income-is-gross --currency USD` and assigns prefixed IDs. It maps English month names + day/year to ISO dates, keeps only required product/customer fields, and converts source decimals to integer cents without silently rounding. Under those assumptions the 100 sample sale lines reconcile to 479 units, gross 51,680,000 cents, discounts 2,345,600 cents, and net 49,334,400 cents. Those are illustrative assumptions, not market or actual business amounts.
