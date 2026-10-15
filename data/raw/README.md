# Raw data

Put the source files in this folder, unchanged from the download. The pipeline finds each one by its file name.

| Dataset | Source | File name the pipeline looks for |
|---|---|---|
| Monthly personal and cash remittances | BSP | `Original_ofwp.xlsx`, or `ofwp.xlsx` |
| Cash remittances by country and source (one sheet per year) | BSP | `Original_ofw.xlsx`, or `ofw.xlsx` |
| Peso per US dollar exchange rate (the workbook with the monthly, annual and daily sheets) | BSP | `Original_ExchangeRate_whole.xlsx`, or `pesodollar.xlsx` |
| Year-on-year change of the CPI, all items, Philippines (2018=100) | PSA OpenSTAT | `Original_PSA_PriceIndices.csv`, or the default export name starting with `0012M4ACP23` |

`Original_Inflation_whole.xlsx` is the full PSA table for every region and commodity group. The pipeline does not read it; the CSV above holds the one row that is used.

The exchange-rate file must include the 2018 months. They are the base for the year-on-year change of the 2019 months.

To check that every file is found:

```
.venv\Scripts\python -m remittrend.pipeline check
```

`artifacts/manifest.json`, written by the pipeline's `report` stage, records each file's checksum, the months it covers and when the workbook was last saved by its publisher.

BSP marks the 2025 and 2026 remittance figures as preliminary, so also note the date each file was downloaded:

| File | Downloaded on |
|---|---|
| | |

## Reference files

`data/reference` holds the group's own cleaned versions of the exchange rate and inflation series (`Merge_*.csv`) and the merged monthly dataset (`remittrend_monthly_dataset_v2.xlsx`). The pipeline does not read them. The tests compare the pipeline's output against them.
