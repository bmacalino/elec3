# Second round of improvements

This document records what was changed after the first complete build of RemitTrend PH, why, and what each change did to the results. It is for the group: use it when updating the paper and when a panel member asks why something is done the way it is.

All figures are for the dataset that ends in June 2026. To reproduce them, run `.venv\Scripts\python -m remittrend.pipeline all`.

## What changed, in one table

| Area | Before | Now | Effect on the results |
|---|---|---|---|
| Main model | Lowest RMSE on one 12-month test | Lowest RMSE averaged over five test windows | Main model is XGBoost, not Random Forest |
| Significance | Not tested | Diebold–Mariano test against the main model | Random Forest cannot be told apart from XGBoost; SARIMA can |
| Model settings in the rolling check | Chosen once, reused | Chosen again for each window | The rolling results no longer use hindsight |
| Prediction intervals | Statistical models only | Every model | The main forecast now has a 95% range |
| Stationarity | ADF | ADF and KPSS | The tests disagree on two indicators, which led to a new check |
| Relationship finding | One test run | Three: whole period, from 2022, indicators not differenced | Same conclusion every time: no predictive link |
| Study period | Fixed at June 2026 | Ends at the latest month in all three series | New months are picked up without editing code |
| Paper outputs | None | 13 tables and 8 figures in `paper/`, and a notebook | |
| Reproducibility | None | `artifacts/manifest.json` | |
| Dashboard | | Dark mode, shareable links, more downloads, smaller chart library | |

## 1. Forecasting

### 1.1 The main model is chosen on five windows

**The problem.** On the 12 test months, Random Forest beat XGBoost by 23.00 to 23.04, a difference of US$0.04 million. A choice that close depends on which 12 months happen to be the test.

**The change.** Each model forecasts 12 months from five starting points, six months apart: June 2023, December 2023, June 2024, December 2024 and June 2025. The last one is the original test. The main model is the one with the lowest RMSE averaged over the five.

**The result.**

| Model | Average RMSE, five windows | RMSE, latest window |
|---|---|---|
| XGBoost | 16.9 | 23.0 |
| Random Forest | 18.6 | 23.0 |
| SARIMA | 25.6 | 29.6 |
| XGBoost with indicators | 30.1 | 54.3 |
| Random Forest with indicators | 38.3 | 96.6 |
| SARIMAX | 43.0 | 29.3 |
| Same month last year (reference) | 88.1 | 89.9 |
| ARIMA | 202.6 | 215.4 |
| ARIMAX | 216.9 | 212.2 |

US$ million. XGBoost is now the main model.

**Be open about this in the paper.** The rule was changed after the first results were seen. Report both: Random Forest is marginally ahead on the latest window alone, and XGBoost is ahead on the average of five. To keep the proposal's original rule instead, set `MODEL_SELECTION = "test"` in `remittrend/config.py` and run the pipeline again; Random Forest becomes the main model.

### 1.2 A test of whether the models really differ

The Diebold–Mariano test asks whether two models' forecast errors differ by more than chance. It is run on the 60 monthly forecasts of the five windows, each model against the main model. A p-value below 0.05 means the model is less accurate than the main model by more than chance.

| Model | P-value against XGBoost | Reading |
|---|---|---|
| Random Forest | 0.117 | Cannot be told apart |
| SARIMA | 0.005 | Less accurate |
| XGBoost with indicators | 0.044 | Less accurate |
| Random Forest with indicators | 0.138 | Cannot be told apart |
| SARIMAX | 0.039 | Less accurate |
| ARIMA, ARIMAX, same month last year | below 0.001 | Less accurate |

Two things to say when reporting this:

- "Cannot be told apart" is not "equally good". Random Forest with indicators has more than twice the average error of XGBoost. Its error is moderate in four windows and very large in one, and with that much variation the test cannot rule out chance.
- The test is an approximation here. The windows overlap and each contains forecasts from 1 to 12 months ahead, so the errors are correlated. The code allows for this with Newey–West weights over 11 lags and the small-sample correction of Harvey, Leybourne and Newbold. Treat the p-values as supporting evidence, not as the deciding rule.

### 1.3 Settings are chosen again for every window

Before, the ARIMA orders and the tree hyperparameters were chosen once on January 2019 to June 2025 and reused in the earlier windows. A window that starts in June 2023 was therefore scored with settings chosen using data up to 2025.

Now each window's settings are chosen only from the months before it. The ARIMA and SARIMA orders came out the same in all five windows (ARIMA(3,1,3) with drift; SARIMA(1,0,1)(1,1,0)[12] with drift). The tree settings varied, for example the depth of the Random Forest. `paper/tables/08_rolling_windows.csv` lists the settings used in each window.

This takes five times as many searches, so the searches now run on all processor cores. The whole pipeline takes about five minutes on a 12-core laptop.

### 1.4 Every model has a prediction interval

**The problem.** Random Forest and XGBoost produce a single number. The main forecast therefore had no stated uncertainty.

**The change.** The interval is measured from the model's own past errors. The model is refitted as of each of the previous 36 months and asked to forecast the months that are now known. For each band of forecast months (1–3, 4–6, 7–9, 10–12) the interval is the size that would have contained 95% of those errors. This is called a split-conformal interval. The interval never narrows as the forecast reaches further ahead.

Only months before the forecast start are used, so the interval for the test window was measured without seeing the test months.

**How good are the intervals?** On the 12 test months:

| Model | Test months inside the 95% interval | Width |
|---|---|---|
| XGBoost | 12 of 12 | about ±2.4% |
| Random Forest | 12 of 12 | ±1.7% to ±2.4% |
| SARIMA | 12 of 12 | ±5.4% to ±7.2% |
| XGBoost with indicators | 11 of 12 | about ±2.0% to ±2.3% |
| Random Forest with indicators | 4 of 12 | ±1.7% to ±2.9% |

**The main forecast.** XGBoost forecasts US$37.14 billion for July 2026 to June 2027, 3.1% above the previous twelve months. For July 2026 it gives US$3,260.7 million, with a 95% interval of US$3,221.9 to 3,299.4 million.

**Two limits.**

- The tree models' intervals reflect how accurate the models were in the last three years, which were calm. A shock like 2020 would fall outside them. SARIMA's interval is wider because it is estimated from the whole period, including 2020.
- An interval can be badly wrong when the model is. Random Forest with indicators missed 8 of 12 test months.

### 1.5 Why Random Forest forecasts much lower growth

Random Forest forecasts +0.5% for the next twelve months. XGBoost, SARIMA and SARIMAX forecast +2.5% to +3.1%. The cause was traced:

1. Growth has slowed. The year-on-year change fell from 3.5% in January 2026 to 1.7% in June 2026.
2. The only earlier time growth was that low was the 2020 pandemic. When the forest looks for past months resembling the present, about a quarter of the weight falls on 2020, when low growth was followed by a collapse.
3. Each forecast month is fed back in as an input for the next. A low first forecast (1.45%) therefore pulls the following months down to between 0% and 0.9%.

XGBoost is set up to move more cautiously away from the average, so it stays near 3%.

Nothing was changed to "fix" this. It is how the model reads the data, and adjusting a model because its forecast looks wrong would be choosing the answer. The Forecast page shows every model's total side by side so a reader can see the disagreement.

## 2. Relationship with the exchange rate and inflation

### 2.1 A second stationarity test

The ADF test asks whether a series is non-stationary; KPSS asks the opposite. Running both shows where the evidence is weak.

| Series | ADF | KPSS | Together |
|---|---|---|---|
| Cash remittances, year-on-year change | Stationary (p = 0.003) | Stationary | Stationary |
| Peso per US dollar, monthly average | Not stationary (p = 0.88) | Not stationary | Not stationary |
| Peso per US dollar, year-on-year change | Not stationary (p = 0.53) | Stationary | The tests disagree |
| Inflation rate | Not stationary (p = 0.31) | Stationary | The tests disagree |

ADF still decides which series are differenced, as the proposal states. But for the last two rows, differencing is a judgement call, which is the reason for the second check below.

### 2.2 Two checks on the "no relationship" finding

The first run found that neither indicator helps predict remittances. Two things could have produced that result wrongly, so each was tested.

- **The pandemic.** Remittances fell and rebounded sharply in 2020 and 2021, which could hide a real link. The tests were repeated on January 2022 to June 2026 (54 months).
- **Differencing.** Where ADF and KPSS disagree, the tests were repeated with the indicator left as it is.

| Tested on | Lowest Granger p-value, any indicator | Helps predict? |
|---|---|---|
| Whole period | 0.400 | No |
| From January 2022 | 0.075 | No |
| Whole period, the two disputed indicators not differenced | 0.425 | No |

The conclusion is the same all three times. This agrees with the forecasting results: adding the indicators made the average error worse for every pair of models (for example SARIMA 25.6, SARIMAX 43.0).

One caution on wording: the finding is "no evidence of a predictive link in this period", not "there is no link".

## 3. Reproducibility and outputs for the paper

### 3.1 The manifest

`artifacts/manifest.json` is written by the `report` stage. It records the study period, the train/test split, every setting in `config.py`, the main model and the rule that chose it, the software versions, and for each raw file its name, size, a checksum, the months it covers, and when the workbook was last saved.

That last value comes from inside the Excel file. For a file kept as downloaded it shows when the BSP last updated it: the remittance workbook was last saved on 11 September 2026. This dates the figures better than a download date.

The download-date table in `data/raw/README.md` is still blank. Only the person who downloaded the files can fill it in.

### 3.2 Tables and figures

The `report` stage writes these to `paper/`. They are built from the same files the dashboard reads, so the paper and the dashboard cannot disagree.

| Tables (`paper/tables`, CSV) | Figures (`paper/figures`, PNG, 300 dpi) |
|---|---|
| 01 dataset summary | 01 remittances and trend |
| 02 yearly totals | 02 seasonal index |
| 03 seasonal profile | 03 decomposition |
| 04 stationarity tests | 04 indicators |
| 05 lagged correlations | 05 lagged correlations |
| 06 Granger tests | 06 model errors |
| 07 model comparison | 07 actual against predicted |
| 08 rolling windows | 08 forecast |
| 09 indicator effect | |
| 10 test predictions | |
| 11 forecast | |
| 12 sources by year | |
| 13 top countries | |

To change how a figure looks, edit `remittrend/report.py` and run `.venv\Scripts\python -m remittrend.pipeline report`.

### 3.3 The notebook

`notebooks/results.ipynb` shows the same tables and figures in order, grouped by analytical question. It was executed from start to finish without errors. Open it with `.venv\Scripts\python -m jupyter lab`.

### 3.4 Downloads in the dashboard

The Model comparison and Forecast pages now have a Download CSV button, alongside the one on Historical data. The forecast download respects the selected model, number of months and assumed values.

## 4. New months are picked up automatically

The study period was fixed at June 2026 in the code. It now ends at the latest month for which remittances, the exchange rate and inflation all have a value. To add a month: replace the raw files and run the pipeline.

To keep the paper's results fixed while newer files exist, set `STUDY_END = "2026-06"` in `remittrend/config.py`.

Tests that check figures quoted in the proposal are now skipped, with a message, once the files move past June 2026. The BSP revises its preliminary figures, so those checks would otherwise fail for a reason that is not a bug.

## 5. Dashboard

- **Dark mode.** A button at the top right switches theme. The first visit follows the computer's setting; the choice is remembered. Charts redraw in the new colours.
- **Shareable links.** The date range, year, model, number of months and assumed values are kept in the address bar. A view survives a reload and can be sent as a link, for example `/forecast?model=sarimax&exchange_rate=65`.
- **Range of the assumptions.** When the assumed exchange rate or inflation is outside what a model was fitted on, the Forecast page says so and gives the range (inflation 0.5% to 8.7%; peso–dollar rate −6.9% to +15.9% from a year earlier).
- **Forecast range on Overview.** The next-month card shows the 95% interval.
- **Smaller chart library.** A build of Plotly with only the chart types used: 1.45 MB, down from 4.64 MB.
- **Browser-tab icon.** Replaces the default one from the project template.
- **A layout fix.** The wider tables on Model comparison and Relationships pushed those pages sideways. Wide tables now scroll inside their card at every screen width.

## 6. Repository

`data/raw/Original_Inflation_whole.xlsx` (20 MB) is now excluded from git. The pipeline does not read it; the row it needs is in `Original_PSA_PriceIndices.csv`. The file is still on disk.

## What to change in the paper

1. **Model selection (Analytics Techniques; Evaluation Plan).** Replace "the model with the lowest RMSE on the testing period" with "the lowest RMSE averaged over five rolling 12-month test windows, the last of which is the testing period". State that the rule was refined after the first comparison, and report both results.
2. **Rolling windows (Evaluation Plan).** "Where time allows" can go; it was done, with settings chosen again in each window.
3. **Significance (Evaluation Plan).** Add the Diebold–Mariano test.
4. **Prediction intervals (System Features, item 6).** "Prediction intervals are shown for the statistical models" becomes "for every model", with the method for the tree models.
5. **Stationarity (Relationship Analysis).** Add the KPSS test and the two robustness checks.
6. **Limitations.** Add: tree models reason from similar past months, so after an unusual period such as 2020 their forecasts can lean on it; the tree models' intervals reflect recent accuracy only.
7. **Tools.** Add matplotlib (figures for the paper) and joblib.
8. **Still outstanding from the first round.** Bootstrap is replaced by React, Tailwind CSS and shadcn/ui; pmdarima is not used; the tree models predict the year-on-year change; the indicators enter with a three-month lag; a "same month last year" reference row is added.

References you will probably need. Check each against the source before citing.

- Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics, 13*(3), 253–263.
- Harvey, D., Leybourne, S., & Newbold, P. (1997). Testing the equality of prediction mean squared errors. *International Journal of Forecasting, 13*(2), 281–291.
- Kwiatkowski, D., Phillips, P. C. B., Schmidt, P., & Shin, Y. (1992). Testing the null hypothesis of stationarity against the alternative of a unit root. *Journal of Econometrics, 54*(1–3), 159–178.
- Lei, J., G'Sell, M., Rinaldo, A., Tibshirani, R. J., & Wasserman, L. (2018). Distribution-free predictive inference for regression. *Journal of the American Statistical Association, 113*(523), 1094–1111.

## Settings

All in `remittrend/config.py`. Run the pipeline after changing one.

| Setting | Value | What it does |
|---|---|---|
| `STUDY_END` | `None` | `None`: end at the latest month in all three series. A month such as `"2026-06"` freezes the period |
| `MODEL_SELECTION` | `"rolling"` | `"rolling"`: average over the windows. `"test"`: the latest window only |
| `ROLLING_WINDOWS`, `ROLLING_STEP` | 5, 6 | Number of test windows and months between them |
| `INTERVAL_BACKTEST_ORIGINS` | 36 | Past forecasts used to measure the tree models' intervals |
| `RELATIONSHIP_RECENT_START` | `"2022-01"` | Start of the post-pandemic check |
| `INDICATOR_LAG` | 3 | Months by which the indicators lag in the models |

## How this was checked

- 141 automated tests pass. New ones cover the significance test, the intervals (including that they use only earlier months), the selection rule, both robustness checks, the automatic study period, the exports and the manifest.
- Every generated file was deleted and rebuilt from the raw files in one run.
- All eight pages were opened in a browser at desktop and phone width in light mode. There were no errors and no page scrolled sideways. Pages were also opened through links carrying filters, to confirm those are applied.
- The dark theme was looked at on three pages: Overview, Seasonality and Model comparison.
- The notebook was executed from start to finish.

Not done: the automated tests cover the API behind the pages, not the pages themselves, and the dark theme was not looked at on the other five pages.
