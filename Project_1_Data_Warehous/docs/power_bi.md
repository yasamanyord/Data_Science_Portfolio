# Power BI handoff

The upgraded warehouse supports a reproducible, read-only monthly aggregate export. This is useful for demonstrating your Excel/Power BI and SQL background without distributing raw customer data. The repository does not include a fabricated .pbix or a claimed cloud report.

## Export

Run from the project folder after a successful quality check:

```bash
python -m warehouse check
python -m warehouse export runtime/monthly.csv
```

The file includes `month`, `net_cents`, `units`, `sales`, `prior_year_net_cents` and `yoy_pct`. USD amounts are integer cents. Missing prior month or denominator yields blank/null. Use a new file path for each export.

## Build in Power BI Desktop

1. Get Data → Text/CSV, select the output, and import it as `Monthly`.
2. In Power Query, convert `month` to a proper date representing the first of each month (append "-01" then set Date); ensure whole-number types for amounts and units. Do not sum the YoY percentage column.
3. Create explicit measures (use the actual table name after importing):

```dax
Net Revenue USD = DIVIDE(SUM(Monthly[net_cents]), 100)
Units Sold = SUM(Monthly[units])
Sale Lines = SUM(Monthly[sales])
Average Sale USD = DIVIDE([Net Revenue USD], [Sale Lines])
```

4. Add a line or column chart by month and Net Revenue USD; cards for the measures; a table with month, units, sale lines and monthly YoY. Show individual monthly comparisons, not aggregated percentages.
5. Compare totals with `python -m warehouse report`. Keep currency and synthetic-data label visible.

The aggregate is monthly only; raw product/customer filtering and distinct customer metrics are supported by the local dashboard/API, not by this monthly CSV. For a real enterprise report, deploy an approved read-only database/semantic model with date dimension, incremental refresh, permissions and independently reconciled measures. Do not upload actual customer data to public BI services.
