# Functional test checklist

Use this checklist to confirm that each feature in the proposal works. Run it on the built app (`.venv\Scripts\python run.py`, then open http://127.0.0.1:5050).

For each case, follow the steps, compare what you see with the expected result, and fill in the last two columns. The expected values are for the dataset that ends in June 2026; they change when new months are added.

The "Automated check" column names the test in `tests/` that checks the same thing. Run all of them with `.venv\Scripts\python -m pytest`.

Tester: ________________  Date: ____________  Browser: ________________

## 1. Data processing

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 1.1 | Raw files are found | Run `.venv\Scripts\python -m remittrend.pipeline check` | All four datasets are listed with a file name; none says MISSING | `test_config.py` | | |
| 1.2 | Dataset is built | Run `.venv\Scripts\python -m remittrend.pipeline ingest` | "Study period 2019-01 to 2026-06: 90 months"; `monthly.csv` has 90 rows | `test_study_period_is_90_months_for_the_proposal_files` | | |
| 1.3 | Dataset matches the group's own cleaned file | Run the tests | `test_monthly_agrees_with_the_group_dataset` passes | same | | |
| 1.4 | Figures match the proposal | Run the tests | 2025 cash remittances US$35.63 billion; December 2024 US$3.38 billion; inflation 8.7% in January 2023 | `test_remittances_match_proposal`, `test_inflation_matches_proposal` | | |
| 1.5 | Paper outputs and manifest | Run `.venv\Scripts\python -m remittrend.pipeline report` | "13 tables, 8 figures" in `paper/`; `artifacts/manifest.json` names the study period and the main model | `test_export_writes_every_table_and_figure`, `test_manifest_records_data_settings_and_software` | | |

## 2. KPI cards (Overview)

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 2.1 | Seven cards are shown | Open Overview | Cards for cash remittances, change from last month, change from last year, year to date, forecast for next month, peso per US dollar, inflation rate | `test_overview_cards_match_the_dataset` | | |
| 2.2 | Latest value is correct | Compare the first card with the last row on Historical data | US$3.04 billion for June 2026 (3,038.5 in the table) | same | | |
| 2.3 | Changes are correct | Read the second and third cards | +12.0% from May 2026; +1.7% from June 2025 | same | | |
| 2.4 | Each card has an up or down indicator | Look at the arrow on each card | An arrow and a signed figure on every card; the exchange rate and inflation arrows are grey, not green or red | same | | |
| 2.5 | Forecast card uses the main model | Compare the fifth card with the first row on Forecast | Same value; the card names the main model and gives a "Likely between" range equal to that row's 95% interval | `test_overview_forecast_card_uses_the_main_model` | | |

## 3. Historical data

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 3.1 | Four charts and a table are shown | Open Historical data | Charts for remittances, exchange rate, exchange rate change, inflation; a table of 90 months | `test_history_respects_the_date_range` | | |
| 3.2 | Date range filter | Choose From Jan 2024 and To Dec 2024 | Charts and table show the 12 months of 2024 only | same | | |
| 3.3 | Quick ranges | Click "Last 12 months" | Range becomes Jul 2025 to Jun 2026 | | | |
| 3.4 | Download | With 2024 selected, click Download CSV and open the file | A file named `remittrend_2024-01_to_2024-12.csv` with 12 rows | `test_history_csv_download_respects_the_date_range` | | |
| 3.5 | Preliminary figures are marked | Scroll the table to 2025 | Months from January 2025 say "(preliminary)" | | | |

## 4. Trends and percentage change

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 4.1 | Direction is reported | Open Trends | Direction card says Rising, with the yearly change of the 12-month average | `test_trend_direction_ignores_the_seasonal_cycle` | | |
| 4.2 | Moving averages | Look at the first chart | Monthly values with 3-, 6- and 12-month averages; a legend names each line | | | |
| 4.3 | Period summary | Choose Jan 2025 to Dec 2025 | Total US$35.63 billion, 12 months | `test_trends_summarise_the_selected_period` | | |
| 4.4 | Yearly change | Read the Yearly totals table | 2025: +3.3%; 2019: "No earlier year"; 2026 is labelled January–June | `test_trends_match_the_proposal` | | |

## 5. Seasonality

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 5.1 | Peak months are named | Open Seasonality | "Usually highest in" starts with Dec | `test_decomposition_adds_up_and_december_is_the_peak` | | |
| 5.2 | Seasonal index chart | Look at the first chart | Twelve bars drawn up or down from 100; December is the tallest, about 115.6; months above 100 are coloured | `test_seasonal_index_recovers_a_known_pattern` | | |
| 5.3 | Heat map | Switch between the two tabs | Month-by-year grid in both views; December is the strongest column | | | |
| 5.4 | Decomposition | Look at the three small charts | Trend, seasonal and remainder charts are shown | same as 5.1 | | |

## 6. Relationship analysis

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 6.1 | Caution is shown | Open Relationships | A notice says the results show association, not cause | | | |
| 6.2 | Side-by-side series | Look at the first three charts | Remittances, exchange rate change and inflation on a year-on-year basis | | | |
| 6.3 | Lagged correlations | Look at the three bar charts | Bars for lags 0 to 12 for each indicator, with a sentence naming the strongest lag | `test_lagged_correlation_and_granger_find_a_known_lag` | | |
| 6.4 | Granger results | Read the Granger table | P-values for 1 to 6 lags and a Yes/No verdict for each indicator | `test_relationship_analysis_of_real_data` | | |
| 6.5 | Robustness checks | Read "Do the results hold under other choices?" | Each indicator is tested on the whole period and from January 2022; two are also tested without differencing; every row says No | `test_relationship_checks_reuse_the_same_tests`, `test_relationships_page_reports_the_robustness_checks` | | |
| 6.6 | Feature importance | Look at the two importance charts | Bars for the Random Forest and XGBoost models with indicators, with a colour legend | `test_tree_models_forecast_in_us_dollars` | | |
| 6.7 | With and without indicators | Read "Do the indicators improve the forecasts?" | Four pairs with the average RMSE without and with indicators; every pair says "Higher error" | `test_saved_comparison_follows_the_selection_rule` | | |
| 6.8 | Stationarity tests | Read the last table | ADF and KPSS p-values for each series as it is and as a month-to-month change, and what the two say together | `test_kpss_agrees_with_adf_on_clear_cases` | | |

## 7. Forecasting

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 7.1 | Default forecast | Open Forecast | Main model selected, 12 months, July 2026 to June 2027, a shaded 95% interval | `test_forecast_defaults_to_the_main_model_and_twelve_months` | | |
| 7.2 | Choose a model | Select SARIMA | Chart and table change to SARIMA; its interval is wider than the main model's | `test_every_model_forecasts_with_an_interval` | | |
| 7.3 | Choose the horizon | Select 6 months | Table has 6 rows | same | | |
| 7.4 | Every model forecasts | Select each of the eight models in turn | A forecast with a 95% interval is shown for each | `test_saved_forecasts_cover_every_model` | | |
| 7.5 | Assumed values change the forecast | Select SARIMAX, enter 70 and 10, click Apply assumptions | An "Effect of the assumptions" column appears; the first 3 months show 0.0, later months do not | `test_assumptions_change_only_models_that_use_the_indicators` | | |
| 7.6 | Assumed values do not affect a model without indicators | Keep 70 and 10, select SARIMA | A notice says the values do not affect this model; the effect column is all 0.0 | same | | |
| 7.7 | Values outside the fitted range are flagged | Select XGBoost with indicators, enter 75 and 12, apply | A notice says the values are outside what the model was fitted on, and gives the range | `test_forecast_reports_values_outside_the_fitted_range` | | |
| 7.8 | Invalid input is refused | Enter `abc` as the exchange rate and apply | A message says the exchange rate must be a number; the previous forecast stays on screen | `test_bad_forecast_requests_are_rejected` | | |
| 7.9 | Clear | Click Clear | Inputs empty; forecast returns to the default | | | |
| 7.10 | Download | Select SARIMAX and 6 months, click Download CSV | A file named `remittrend_forecast_sarimax_2026-07_to_2026-12.csv` with 6 rows | `test_forecast_csv_download_matches_the_page` | | |

## 8. Model comparison

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 8.1 | Metrics for every model | Open Model comparison | Average RMSE, MAE, RMSE and MAPE for eight models and the "Same month last year" reference | `test_models_page_ranks_by_the_selection_rule` | | |
| 8.2 | Best model is identified | Read the first table | The first row has the lowest average RMSE and the "Main model" badge | `test_saved_comparison_follows_the_selection_rule` | | |
| 8.3 | Significance | Read the "Against the main model" column | Every other model has a p-value and says "Cannot be told apart" or "Less accurate" | `test_saved_comparison_tests_every_model_against_the_main_one` | | |
| 8.4 | Interval coverage | Read the "Test months inside the 95% interval" column | A count out of 12 for each of the eight models; the main model's is 12 of 12 | `test_saved_comparison_has_an_interval_for_every_candidate` | | |
| 8.5 | Each test window | Read "Error in each test window" | Five columns, June 2023 to June 2025, and an average | `test_rolling_origins_for_the_proposal_files` | | |
| 8.6 | Actual against predicted | Select another model in the Model list | Chart title and predictions table change to that model | same as 8.1 | | |
| 8.7 | Models cannot see the test months | Run the tests | `test_evaluation_cannot_see_the_test_months` passes | same | | |
| 8.8 | Download | Click Download CSV on the first table | A file with one row per model, the main model first | `test_models_csv_download` | | |

## 9. Historical and forecast comparison

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 9.1 | Observed and forecast on one chart | Open Overview or Forecast | One line for observed months, one for the forecast, joined at June 2026, with a legend | | | |
| 9.2 | Month-by-month comparison | Read the Forecast by month table | Each forecast beside the same month a year earlier, with the change | | | |
| 9.3 | Models side by side | Read "How the models compare" on Forecast | Eight models with their forecast totals; the main model is first | `test_forecast_defaults_to_the_main_model_and_twelve_months` | | |

## 10. Source and country comparison

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 10.1 | Land-based and sea-based | Open Sources and countries | A chart with two lines and a yearly table; 2025: land-based 28,494.8, sea-based 7,139.0 | `test_sources_match_the_proposal_for_2025` | | |
| 10.2 | Main countries | Read the 2025 table | United States of America 39.7%, Singapore 7.3%, Saudi Arabia 6.6% | same | | |
| 10.3 | Choose a year | Select 2026 | Headings say January–June 2026; changes compare with January–June 2025 | same | | |

## 11. Dashboard

| No. | Test case | Steps | Expected result | Automated check | Actual result | Pass |
|---|---|---|---|---|---|---|
| 11.1 | Navigation | Click each of the eight items in the sidebar | Each page opens; the current page is highlighted | `test_page_routes_fall_back_to_index` | | |
| 11.2 | Chart tooltips | Move the pointer over any line chart | A tooltip shows the month and the value of each line | | | |
| 11.3 | Narrow screen | Make the window as narrow as a phone | The sidebar becomes a menu button; pages do not scroll sideways; wide tables scroll inside their card | | | |
| 11.4 | Works offline | Disconnect from the internet and reload | Every page still loads | | | |
| 11.5 | Missing data is explained | Rename the `artifacts` folder, reload Overview, then rename it back | The page lists which files are missing and the command to create them | `test_data_route_reports_what_is_missing` | | |
| 11.6 | Dark mode | Click the moon button at the top right, then reload | The page and every chart switch to dark colours, and stay dark after the reload | | | |
| 11.7 | A view can be shared | On Historical data choose Jan 2024 to Dec 2024, copy the address, open it in a new tab | The new tab opens with the same range selected | | | |

## Summary

| Section | Cases | Passed | Failed |
|---|---|---|---|
| 1. Data processing | 5 | | |
| 2. KPI cards | 5 | | |
| 3. Historical data | 5 | | |
| 4. Trends | 4 | | |
| 5. Seasonality | 4 | | |
| 6. Relationship analysis | 8 | | |
| 7. Forecasting | 10 | | |
| 8. Model comparison | 8 | | |
| 9. Historical and forecast comparison | 3 | | |
| 10. Source and country comparison | 3 | | |
| 11. Dashboard | 7 | | |
| **Total** | **62** | | |
