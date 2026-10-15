# RemitTrend PH

Overseas Filipino cash remittance forecasting and trend analytics system. The proposal is `RemitTrend_PH_Revised_Flask_v5.docx`.

The project has three parts:

- `remittrend/` is the pipeline. It reads the raw BSP and PSA files and writes the cleaned dataset, the analysis results, the trained models, the forecasts, and the tables and figures for the paper.
- `app/` is the Flask API. It serves those results as JSON under `/api`, and serves the built frontend.
- `frontend/` is the dashboard: React, Tailwind CSS and shadcn/ui, with Plotly for charts.

## Setup

You need Python 3.11 and Node 20 or later. From the project folder, in PowerShell:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
npm --prefix frontend install
```

The raw data files are in `data/raw`. `data/raw/README.md` lists them.

## Run

```
.venv\Scripts\python -m remittrend.pipeline all
npm --prefix frontend run build
.venv\Scripts\python run.py
```

Open http://127.0.0.1:5050. Once the frontend is built, the app runs without an internet connection.

The first command takes about five minutes, most of it choosing the model settings for each test window. Run it again whenever a raw file changes. The fitted models it saves in `artifacts/models` are not kept in git, so run it once on each computer.

## The pipeline

`python -m remittrend.pipeline all` runs five stages in order. Each can also be run by name.

| Stage | Reads | Writes |
|---|---|---|
| `check` | `data/raw` | nothing; reports whether each raw file is found |
| `ingest` | `data/raw` | `data/processed/monthly.csv`, `by_source.csv`, `by_country.csv` |
| `analyze` | `monthly.csv` | `artifacts/analysis.json`: seasonality and relationship results |
| `train` | `monthly.csv` | `artifacts/metrics.json`, `artifacts/forecasts.json`, `artifacts/models/` |
| `report` | all of the above | `paper/tables/*.csv`, `paper/figures/*.png`, `artifacts/manifest.json` |

The settings are in `remittrend/config.py`: how the main model is chosen, the number of test windows, the indicator lag, and whether the study period is frozen. `docs/improvements.md` explains each one.

## Adding a new month

Replace the files in `data/raw` with newer downloads and run the pipeline. The study period ends at the latest month that remittances, the exchange rate and inflation all cover, so it extends by itself.

To keep a paper's results fixed while newer files exist, set `STUDY_END` in `remittrend/config.py`, for example `STUDY_END = "2026-06"`.

## For the paper

- `paper/tables` and `paper/figures` hold the result tables (CSV) and figures (PNG, 300 dpi). They are rebuilt by the `report` stage from the same files the dashboard reads.
- `notebooks/results.ipynb` shows them in order, by analytical question. Open it with `.venv\Scripts\python -m jupyter lab`.
- `artifacts/manifest.json` records the study period, settings, raw files and software versions behind the current results.
- `docs/improvements.md` explains the methods added after the first build and lists the edits the paper needs.

## Develop

Run the API and the frontend in two terminals. The second one reloads the page as you edit, and forwards `/api` to Flask.

```
.venv\Scripts\python run.py
npm --prefix frontend run dev
```

Open the address Vite prints, normally http://localhost:5173.

To add a shadcn/ui component, run `npx shadcn@latest add <name>` inside `frontend/`.

Charts are described in Python (`app/figures.py`) and drawn by one React component (`frontend/src/components/chart.tsx`), which applies the colours and fonts of the interface in light and dark mode. Each page keeps its filters in the address bar (`frontend/src/lib/query.ts`), so a view can be reloaded or shared as a link.

## Test

```
.venv\Scripts\python -m pytest
npm --prefix frontend run build
```

The build fails on any TypeScript error, so it is the frontend's check. `docs/functional-tests.md` is the checklist for testing each feature by hand, and `docs/uat-questionnaire.md` is the form for user acceptance testing.

Tests that compare against figures quoted in the proposal are skipped once the raw files go past June 2026, because the BSP revises its preliminary figures.

## Port

The app uses port 5050. To change it, edit `PORT` in `run.py` and the proxy address in `frontend/vite.config.ts`.
