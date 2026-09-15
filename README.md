# FreightIQ — Complete Setup & Run Guide

> **Scope:** Phase 1 project scaffolding/data modeling + Phase 2 ingestion/feature pipeline (`backend/`), plus Phase 3 forecasting, Phase 4 optimization/recommendation, and Phase 5 API layer/auth (`recommendation/`).
>
> This README consolidates the setup, database initialization, reference/synthetic data seeding, and acceptance checks for both services in this repository.

---

## 1. Project Overview

FreightIQ is currently organized in phases, split across two service trees in this repository: `backend/` (Phase 1–2) and `recommendation/` (Phase 3–5).

The `backend/` Phase 1 stack provides a running local environment with:

- FastAPI API skeleton
- PostgreSQL/TimescaleDB
- Redis
- Celery worker infrastructure
- SQLAlchemy ORM models
- Alembic migrations
- Reference-data seed files
- Synthetic historical data generation

`backend/` Phase 2 adds:

- Data ingestion connectors
- Synthetic fallback ingestion
- Data validation
- Data-quality logging
- Feature snapshots
- Feature-engineering pipelines
- Celery Beat ingestion scheduling
- The `get_training_panel()` contract handed to Phase 3

The `recommendation/` service picks up from that handoff:

- **Phase 3** — quantile forecasting models (LightGBM, Prophet, SARIMAX, TFT/Chronos stubs) behind a common `base_forecaster.py` interface, a filesystem-backed model registry with champion/challenger promotion, and an inference service with a naive seasonal-average fallback when no model is trained yet.
- **Phase 4** — port/vessel physical feasibility constraints, a PuLP quick solver plus an OR-Tools CP-SAT multi-parcel solver, Spot/COA/Period scenario simulation, a rule-based risk engine, and the `RecommendationService` that ties all of it together into a single explainable recommendation.
- **Phase 5** — the full REST API surface over Phases 3–4: ports/vessels/trade-lane reference endpoints, standalone scenario comparison, charter contract CRUD, per-lane risk, minimal OAuth2/JWT auth, rate limiting, and request logging.

`recommendation/` currently runs as its own FastAPI service (its own `main.py`, Celery app, and — for local/standalone use — its own SQLite-by-default database) rather than as a module inside `backend/app`. See Section 24 for why that matters before Phase 6.

---

## 2. Repository Structure

The documented repository structure is:

```text
freightiq/
├── docker-compose.yml        # postgres+timescaledb, redis, api, worker
├── .env.example
└── backend/
    ├── pyproject.toml
    ├── Dockerfile
    ├── alembic/               # migration environment
    │   └── versions/
    │       ├── 0001_init_schema.py
    │       └── 0002_phase2_data_quality_and_feature_snapshots.py
    ├── app/
    │   ├── config.py          # Pydantic Settings, env-driven
    │   ├── celery_app.py      # Celery app instance
    │   ├── db/
    │   │   ├── models.py      # SQLAlchemy ORM models
    │   │   └── session.py
    │   ├── schemas/
    │   │   ├── port.py
    │   │   ├── vessel.py
    │   │   ├── contract.py
    │   │   ├── forecast.py
    │   │   └── recommendation.py
    │   ├── ingestion/
    │   │   ├── exceptions.py
    │   │   ├── models.py
    │   │   ├── lookups.py
    │   │   ├── synthetic.py
    │   │   ├── base_connector.py
    │   │   ├── connectors/
    │   │   │   ├── bdi_proxy_connector.py
    │   │   │   ├── bunker_price_connector.py
    │   │   │   ├── commodity_price_connector.py
    │   │   │   ├── ais_connector.py
    │   │   │   ├── port_congestion_connector.py
    │   │   │   └── tide_connector.py
    │   │   ├── validation/
    │   │   │   └── expectations.py
    │   │   └── tasks.py
    │   ├── features/
    │   │   ├── models.py
    │   │   ├── feature_store.py
    │   │   └── pipelines/
    │   │       ├── lag_features.py
    │   │       ├── seasonality_features.py
    │   │       ├── macro_features.py
    │   │       └── build_training_panel.py
    │   └── main.py            # FastAPI app, /health, /health/db
    ├── scripts/
    │   ├── seed_reference_data.py
    │   ├── synthetic_data_generator.py
    │   └── seed_synthetic_data.py
    └── seed_data/
        ├── vessel_classes.yaml
        ├── commodities.yaml
        ├── ports.yaml
        └── trade_lanes.yaml
```

The `recommendation/` (Phase 3–5) service structure:

```text
recommendation/
├── pyproject.toml
├── requirements.txt
├── demo_phase3.py
├── app/
│   ├── config.py             # Settings incl. AUTH_ENABLED, rate limiting, MILP/idle params
│   ├── auth.py                # password hashing + JWT (Phase 5)
│   ├── deps.py                 # get_db / get_current_user / require_role (Phase 5)
│   ├── main.py                # FastAPI app: all routers, CORS, rate limiting, request logging
│   ├── worker.py              # Celery app: training / solver queues
│   ├── api/routers/
│   │   ├── auth.py            # POST /auth/token, GET /auth/me
│   │   ├── ports.py           # GET /ports, /ports/{id}, /ports/{id}/constraints
│   │   ├── vessels.py         # GET /vessels/classes, /vessels/trade-lanes
│   │   ├── forecasts.py       # GET /forecasts, POST /forecasts/models/train, /forecasts/jobs/{id}
│   │   ├── recommendations.py # POST /recommend, /recommend/batch, /recommend/idle-mitigation
│   │   ├── scenarios.py       # POST /scenarios/compare
│   │   ├── contracts.py       # CRUD /contracts
│   │   └── risk.py            # GET /risk/{lane_id}
│   ├── db/
│   │   ├── models.py          # VesselClass, Port, TradeLane, ModelRegistry, Forecast,
│   │   │                      # Recommendation, User, CharterContract
│   │   └── session.py         # engine/session + init_db() reference-data + default-user seeding
│   ├── schemas/                # Pydantic request/response models per router
│   ├── features/               # training-panel access for this service
│   ├── forecasting/            # base_forecaster, registry, inference_service, training_job,
│   │                           # models/ (lightgbm_quantile, prophet, sarimax, tft, chronos)
│   └── optimization/            # constraints, quick_solver, milp_solver, scenario_simulator,
│                                # risk_engine, idle_mitigation, recommendation_service
├── scripts/verify_matrix.py
├── seed_data/
└── tests/
```

---

## 3. Prerequisites

The documented local stack is Docker-based and consists of:

- PostgreSQL/TimescaleDB
- Redis
- FastAPI API
- Celery worker

The repository also expects the Python project/dependencies defined in `backend/pyproject.toml`.

Phase 2 additionally requires:

```text
numpy
geoalchemy2
```

`numpy` is used by the synthetic random-walk/seasonal generators, and `geoalchemy2` provides `WKTElement` for writing `ais_positions.location`. `geoalchemy2` may already be present transitively through the PostGIS/`Port.location` setup, so check before adding a duplicate pin.

---

## 4. Environment Configuration

From the repository root:

```bash
cp .env.example .env
```

Then configure `.env` according to the settings expected by `app/config.py`.

Phase 2 connector code assumes settings corresponding to:

```text
trading_economics_api_key
eia_api_key
aishub_api_key
marinetraffic_api_key
incois_api_key
use_synthetic_data
```

The exact environment-variable names and aliases are determined by the project's `Settings` implementation.

### Synthetic mode

The current Phase 2 implementation is designed to exercise the **synthetic fallback path** end-to-end.

Real source fetch/scraping methods are intentionally stubbed at this stage, so API keys alone do not make those connectors live.

---

## 5. Start the Local Stack

From the repository root:

```bash
docker compose up -d
```

This starts the documented local services:

- PostgreSQL/TimescaleDB
- Redis
- API
- Celery worker

Check the API/database health endpoint:

```bash
curl localhost:8000/health/db
```

The FastAPI application exposes `/health` and `/health/db`.

---

## 6. Initialize the Database

Run the Alembic migrations from inside the API container:

```bash
docker compose exec api alembic upgrade head
```

This applies the Phase 1 schema and the Phase 2 migration.

### Phase 2 migration

Phase 2 adds:

```text
data_quality_log
feature_snapshots
```

The Phase 2 migration is:

```text
backend/alembic/versions/0002_phase2_data_quality_and_feature_snapshots.py
```

Its `down_revision` is expected to point to:

```text
0001_init_schema
```

If the Phase 1 migration in the actual repository uses a different revision ID, the Phase 2 migration must use that actual revision ID.

---

## 7. Seed Reference Data

After migrations:

```bash
docker compose exec api python scripts/seed_reference_data.py
```

The reference seed files are:

```text
backend/seed_data/
├── vessel_classes.yaml
├── commodities.yaml
├── ports.yaml
└── trade_lanes.yaml
```

This establishes the reference entities required by the rest of the system.

---

## 8. Seed Synthetic Historical Data

Seed five years of synthetic historical data:

```bash
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

Synthetic time-series rows are explicitly marked:

```text
data_provenance='synthetic'
```

so they are not presented with the same confidence as live data.

The documented Phase 1 acceptance state expects populated data for:

- `vessel_classes`
- `ports`
- `trade_lanes`
- `commodities`
- the five time-series tables
- `vessels`
- `ais_positions`
- `charter_contracts`
- `voyage_simulations`

Three output-oriented tables are intentionally empty at this stage:

- `model_registry`
- `forecasts`
- `recommendations`

Those are outputs of later phases and are not supposed to be populated with invented records.

---

## 9. Phase 2 Celery Configuration

Phase 2 requires one change to `backend/app/celery_app.py`.

If the Celery application currently has:

```python
include=[]
```

change it to:

```python
celery_app = Celery(
    "freightiq",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.ingestion.tasks"],
)
```

The purpose is to make the worker discover the ingestion tasks.

Nothing else in `celery_app.py` needs to change according to the Phase 2 notes.

`app/ingestion/tasks.py` registers its Beat schedule using:

```python
celery_app.conf.beat_schedule.update(...)
```

at import time, so the schedule becomes active once the module is included.

---

## 10. Phase 2 Ingestion Components

Phase 2 introduces the following ingestion components:

```text
backend/app/ingestion/
├── exceptions.py
├── models.py
├── lookups.py
├── synthetic.py
├── base_connector.py
├── connectors/
│   ├── bdi_proxy_connector.py
│   ├── bunker_price_connector.py
│   ├── commodity_price_connector.py
│   ├── ais_connector.py
│   ├── port_congestion_connector.py
│   └── tide_connector.py
├── validation/
│   └── expectations.py
└── tasks.py
```

Their documented roles are:

- `exceptions.py` — source/validation exceptions
- `models.py` — `data_quality_log`
- `lookups.py` — cached foreign-key lookups
- `synthetic.py` — synthetic fallback tier
- `base_connector.py` — connector orchestration
- `connectors/` — individual data-source connectors
- `validation/expectations.py` — Pandera schemas
- `tasks.py` — Celery tasks and Beat schedule registration

---

## 11. Phase 2 Feature Pipeline

Phase 2 also introduces:

```text
backend/app/features/
├── models.py
├── feature_store.py
└── pipelines/
    ├── lag_features.py
    ├── seasonality_features.py
    ├── macro_features.py
    └── build_training_panel.py
```

The key Phase 2 → Phase 3 interface is:

```python
get_training_panel()
```

from:

```text
app.features.pipelines.build_training_panel
```

This produces the training panel that Phase 3 can consume.

---

## 12. Run the Phase 2 Acceptance Check

There are two documented ways to exercise Phase 2.

### Option A — synchronous, no broker required

From the backend environment:

```bash
python -c "
from app.ingestion.tasks import run_all
print(run_all.run())
"
```

This exercises the same `run()` path without requiring a running Celery broker.

If executing from outside the API container, make sure the Python environment has the project installed and the backend is on the Python import path.

### Option B — Celery worker + Beat

Start the worker:

```bash
celery -A app.celery_app worker --loglevel=info &
```

Start Beat:

```bash
celery -A app.celery_app beat --loglevel=info &
```

Beat is responsible for the scheduled ingestion tasks registered by Phase 2.

---

## 13. Verify the Training Panel

After the Phase 2 ingestion/features path has run:

```bash
python -c "
from datetime import date
from app.features.pipelines.build_training_panel import get_training_panel
df = get_training_panel(date.today())
print(df.shape)
print(sorted(df.columns))
"
```

A successful run should print the resulting DataFrame shape and its sorted column names.

`get_training_panel()` is the documented handoff point from Phase 2 into Phase 3.

---

## 14. Recommended Complete Startup Sequence

For a fresh local environment, the documented sequence is:

### Step 1 — Configure environment

```bash
cp .env.example .env
```

### Step 2 — Start services

```bash
docker compose up -d
```

### Step 3 — Apply all migrations

```bash
docker compose exec api alembic upgrade head
```

### Step 4 — Seed reference data

```bash
docker compose exec api python scripts/seed_reference_data.py
```

### Step 5 — Seed five years of synthetic data

```bash
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

### Step 6 — Verify DB/API health

```bash
curl localhost:8000/health/db
```

### Step 7 — Ensure Celery imports Phase 2 tasks

Verify `backend/app/celery_app.py` contains:

```python
include=["app.ingestion.tasks"]
```

### Step 8 — Run Phase 2 ingestion

For a synchronous check:

```bash
python -c "
from app.ingestion.tasks import run_all
print(run_all.run())
"
```

Or start Celery:

```bash
celery -A app.celery_app worker --loglevel=info &
celery -A app.celery_app beat --loglevel=info &
```

### Step 9 — Verify feature-panel generation

```bash
python -c "
from datetime import date
from app.features.pipelines.build_training_panel import get_training_panel
df = get_training_panel(date.today())
print(df.shape)
print(sorted(df.columns))
"
```

---

## 15. Data Source / Synthetic Fallback Status

**Important:** the current Phase 2 implementation does not yet contain real API/scraper implementations.

The following connector methods are intentionally stubs:

- `_fetch_*`
- `_scrape_*`
- `_parse_*`

They raise `NotImplementedError` by design.

Therefore, the current acceptance path is based on the **synthetic fallback**.

Real API clients can later be wired into the individual connector methods without changing the overall connector architecture.

---

## 16. Important Phase 2 Modeling Assumptions

The Phase 2 implementation makes several explicit assumptions.

### 16.1 Declarative Base

`app/ingestion/models.py` and `app/features/models.py` attempt to import:

```python
from app.db.base import Base
```

and fall back to:

```python
from app.db.models import Base
```

If the project's actual declarative base lives elsewhere, those imports need to be adjusted.

### 16.2 Settings names

The connectors assume settings corresponding to the API keys and `use_synthetic_data` listed above. If the project's `Settings` class uses different attribute casing or aliases, connector code needs to be adjusted.

### 16.3 BDI proxy lane mapping

Composite BDI indices such as BCI/BPI/BSI/BHSI are not lane-specific, while `freight_rates` requires a non-null `trade_lane_id`.

The current connector therefore broadcasts each index to every seeded lane for the matching vessel class and tags the source as:

```text
trading_economics_proxy
```

This is a modeling choice, not a schema requirement, and should be revisited if it becomes misleading with real data.

### 16.4 AIS placeholder fleet

The synthetic AIS fallback uses three hardcoded placeholder IMO numbers because the Phase 1 `vessels` table was not described as having a seeded roster.

Once a real vessel roster exists, this should be replaced with a query against `vessels`.

### 16.5 Separate feature snapshot concepts

The new:

```text
feature_snapshots
```

table is distinct from the existing:

```text
Forecast.feature_snapshot
```

JSONB column. They serve different purposes.

---

## 17. Phase 1 Data Provenance

The reference-data provenance documented for Phase 1 is:

- `seed_data/ports.yaml` contains a `source` field per port.
- Paradip and Visakhapatnam figures are citation-backed.
- Other port figures are marked `source: estimated`.
- Those provenance notes are folded into the ports' `notes` column.
- Trade-lane distances are placeholder approximations rather than calculated sea routes.
- Synthetic time-series data is marked with `data_provenance='synthetic'`.

The documented sea-route calculation using the `searoute` package is a Phase 2 ingestion task rather than part of the Phase 1 seed data.

---

## 18. Expected Phase 1 Database State

After:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_reference_data.py
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

the documented acceptance expectation is that the plausibly populated Phase 1 tables have rows.

The following are intentionally empty:

```text
model_registry
forecasts
recommendations
```

This is expected because they represent outputs from later phases:

- `model_registry` — trained/registered models
- `forecasts` — model-generated forecasts
- `recommendations` — optimization-engine recommendations

Their zero counts are therefore not considered an error in Phase 1.

---

## 19. What Is Not Implemented Yet

According to the source documents, the following are explicitly outside the current Phase 2 scope:

1. Real API/scraper implementations for the connector stubs.
2. Great Expectations — Pandera is used instead.
3. Model training.
4. Model inference.
5. Later forecasting/optimization outputs.

The Phase 2 handoff into model training is:

```python
get_training_panel()
```

---

## 20. Quick Reference — Commands

### Initial setup

```bash
cp .env.example .env
docker compose up -d
```

### Database

```bash
docker compose exec api alembic upgrade head
```

### Reference seed

```bash
docker compose exec api python scripts/seed_reference_data.py
```

### Synthetic history

```bash
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

### Health

```bash
curl localhost:8000/health/db
```

### Phase 2 synchronous acceptance

```bash
python -c "
from app.ingestion.tasks import run_all
print(run_all.run())
"
```

### Phase 2 Celery worker

```bash
celery -A app.celery_app worker --loglevel=info
```

### Phase 2 Celery Beat

```bash
celery -A app.celery_app beat --loglevel=info
```

### Training-panel check

```bash
python -c "
from datetime import date
from app.features.pipelines.build_training_panel import get_training_panel
df = get_training_panel(date.today())
print(df.shape)
print(sorted(df.columns))
"
```

---

## 21. Phase Roadmap / Handoff

The current documented progression is:

```text
Phase 1
  ↓
Project scaffolding
Database schema
Reference data
Synthetic historical data
  ↓
Phase 2
  ↓
Ingestion
Validation
Data quality logging
Feature snapshots
Feature engineering
Training panel
  ↓
Phase 3
  ↓
Model training / inference
  ↓
Later phases
  ↓
Forecasting / optimization / recommendations
```

The important Phase 2 contract is:

```text
app.features.pipelines.build_training_panel.get_training_panel()
```

which supplies the training panel for Phase 3.

---

## 22. Troubleshooting / Caveats

### Celery does not discover Phase 2 tasks

Verify:

```python
include=["app.ingestion.tasks"]
```

is present in `app/celery_app.py`.

### Migration fails at Phase 2

Check that the `down_revision` in:

```text
alembic/versions/0002_phase2_data_quality_and_feature_snapshots.py
```

matches the actual Phase 1 migration revision.

### Real APIs are not producing data

This is expected with the current Phase 2 implementation. The real fetch/scrape/parse methods are intentionally stubs and the acceptance path uses synthetic fallback data.

### Some output tables contain zero rows

The following being empty is expected at this stage:

```text
model_registry
forecasts
recommendations
```

They are intended to be populated by later phases rather than by the initial seed process.

---

## 23. Current Definition of Done

The documented Phase 1 + Phase 2 local setup is ready for the next phase when:

- Docker services are running.
- Alembic migrations reach `head`.
- Reference data has been seeded.
- Five years of synthetic history can be seeded.
- `/health/db` succeeds.
- Phase 2 ingestion can execute through `run_all.run()`.
- Celery worker/Beat can discover and schedule ingestion tasks.
- Synthetic fallback ingestion completes end-to-end.
- `get_training_panel(date.today())` returns a DataFrame and its shape/columns can be inspected.

At that point, Phase 2 has established the documented handoff into Phase 3 model training/inference.

---

## 24. `recommendation/` Service — Architecture Note

`recommendation/` is its own FastAPI app, own Celery app (`app/worker.py`), and own `Base`/`DATABASE_URL` (defaults to a local `freightiq.db` SQLite file for standalone runs) rather than a module bolted onto `backend/app`. In practice this means:

- It can be run and tested completely independently of `backend/` (see Section 28) — nothing here requires the Phase 1–2 Docker stack.
- It does **not** currently share `backend/`'s Postgres database, ORM `Base`, or Alembic migrations. Its own `init_db()` (in `app/db/session.py`) creates tables and seeds reference data directly via SQLAlchemy, with a schema-drift check that drops and recreates tables if seed data looks stale.
- The Phase 5 plan's single OpenAPI schema (for `openapi-typescript` frontend client generation in Phase 6) currently means **two** schemas — one at `backend`'s `/api/openapi.json` and one at `recommendation`'s. Before Phase 6, decide whether to merge the two services into one deployable (matching the plan's original "modular monolith" framing) or keep them split and have the frontend consume two typed clients.

---

## 25. Phase 3 — Model Training & Inference

Lives under `recommendation/app/forecasting/`.

- `base_forecaster.py` — common interface every model implements (`fit`, `predict`), so swapping LightGBM for Prophet/SARIMAX/TFT/Chronos is additive.
- `models/` — `lightgbm_quantile.py` (p10/p50/p90 quantile regression, the default champion), `prophet_model.py`, `sarimax_model.py`, plus `tft_model.py` / `chronos_model.py` stubs reserved for the Tier 1 upgrade path.
- `registry.py` (`ModelRegistryManager`) — registers trained models against `model_registry`, and promotes a challenger to active champion only if it beats the current champion by `settings.DEFAULT_RETRAIN_MARGIN_PCT` (default 2%).
- `training_job.py` — `run_model_training_pipeline()`, invoked either synchronously or via the Celery `training` queue (`app.worker.train_models_task`).
- `inference_service.py` (`ForecastingService.get_forecast`) — looks up the active champion for a `(trade_lane_id, vessel_class_id)` pair; if none exists, gracefully degrades to a naive seasonal rolling-average baseline rather than erroring, and persists every forecast (with its feature snapshot) to the `forecasts` table for auditability.
- `backtest.py` / `audit.py` — walk-forward validation and a `GET /forecasts/audit` coverage summary (training row counts, active champions, backtest metrics per lane × vessel class).

**Train models and get a forecast:**

```bash
curl -X POST localhost:8001/api/forecasts/models/train \
  -H "Content-Type: application/json" \
  -d '{"trade_lane_ids": [1], "vessel_class_ids": [3], "target_variable": "TCE_rate"}'

curl "localhost:8001/api/forecasts?trade_lane_id=1&vessel_class_id=3&horizons=7&horizons=30&horizons=90"
```

If no model has been trained yet for a lane/class pair, `GET /forecasts` still returns a result — `model_fallback_used: true` and a `model_fallback_reason` explaining why (Section 5.3's layered-fallback principle).

---

## 26. Phase 4 — Optimization & Recommendation Engine

Lives under `recommendation/app/optimization/`.

- `constraints.py` — `resolve_port_code()` (canonicalizes aliases like `"Paradip"` / `"INPRT"` → `"INPDP"`) and `filter_feasible_lanes_and_vessels()`, which produces a full candidate audit trail (considered / rejected-with-reason / feasible) against usable-capacity and LOA/beam/tide-adjusted-draft constraints.
- `quick_solver.py` — synchronous single-cargo LP pick (PuLP) used by `POST /recommend`.
- `milp_solver.py` — OR-Tools CP-SAT multi-parcel formulation (Section 3.2), used by `POST /recommend/batch` for larger parcel books or when `full_optimization=true`; runs via the Celery `solver` queue when `USE_CELERY=True`.
- `scenario_simulator.py` (`compare_charter_scenarios`) — prices Spot / short-term COA / Period charter side by side (freight, bunker, port dues, risk adjustment) and picks the lowest risk-adjusted cost.
- `risk_engine.py` (`evaluate_risk_flags`) — monsoon/cyclone seasonality, tide-adjusted draft margin, port congestion/demurrage, long-haul transit exposure, and forecast volatility flags.
- `idle_mitigation.py` — Section 3.3 heuristic scorer for backhaul/open-cargo opportunities against an idle vessel.
- `recommendation_service.py` (`RecommendationService`) — orchestrates all of the above into one recommendation with a structured `rationale_json`, persisted to the `recommendations` table.

**Get a recommendation:**

```bash
curl -X POST localhost:8001/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
        "commodity": "coking_coal",
        "cargo_qty_mt": 75000,
        "destination_port_code": "INPRT",
        "laycan_start": "2026-10-01",
        "laycan_end": "2026-10-15"
      }'
```

**Compare Spot vs COA vs Period directly** (independent of a full recommendation — e.g. for re-pricing a different quantity on a known lane/class):

```bash
curl -X POST localhost:8001/api/scenarios/compare \
  -H "Content-Type: application/json" \
  -d '{"trade_lane_id": 1, "vessel_class_id": 3, "cargo_qty_mt": 60000}'
```

**Check risk flags for a lane before submitting a cargo request:**

```bash
curl "localhost:8001/api/risk/1?laycan_start=2026-07-15"
```

---

## 27. Phase 5 — API Layer, Auth & Rate Limiting

Lives under `recommendation/app/api/routers/`, `app/auth.py`, and `app/deps.py`.

### 27.1 Full router surface

| Router | Endpoints |
|---|---|
| `auth.py` | `POST /auth/token`, `GET /auth/me` |
| `ports.py` | `GET /ports`, `GET /ports/{id}`, `GET /ports/{id}/constraints` |
| `vessels.py` | `GET /vessels/classes`, `GET /vessels/classes/{id}`, `GET /vessels/trade-lanes` |
| `forecasts.py` | `GET /forecasts`, `POST /forecasts/models/train`, `GET /forecasts/jobs/{id}`, `GET /forecasts/models`, `GET /forecasts/audit` |
| `recommendations.py` | `POST /recommend`, `POST /recommend/batch`, `GET /recommend/batch/jobs/{id}`, `POST /recommend/idle-mitigation` |
| `scenarios.py` | `POST /scenarios/compare` |
| `contracts.py` | `GET /contracts`, `GET /contracts/{id}`, `POST /contracts`, `PATCH /contracts/{id}`, `DELETE /contracts/{id}` (soft-delete → `CANCELLED`) |
| `risk.py` | `GET /risk/{lane_id}` |

Full interactive docs (OpenAPI/Swagger) render at `/docs` once the service is running; the raw schema is at `/api/openapi.json` for `openapi-typescript` frontend client generation.

### 27.2 Auth

Minimal single-role (`logistics_manager`) OAuth2 password flow + JWT, gated behind `settings.AUTH_ENABLED` (**default `False`**) so local dev, CI, and every read endpoint work unauthenticated out of the box. `User.role` is a free-text column, not an enum, so multi-role RBAC (analyst/manager/admin) is additive later rather than a rewrite — `app/deps.py`'s `require_role(*roles)` dependency already exists for that.

A default account is seeded on first startup: username `logistics_manager` / password `changeme123` (`settings.DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` — rotate both before any non-local deployment).

```bash
# Get a token
curl -X POST localhost:8001/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=logistics_manager&password=changeme123"

# Use it (only enforced once AUTH_ENABLED=true)
curl localhost:8001/api/auth/me -H "Authorization: Bearer <token>"
```

To turn auth enforcement on, set `AUTH_ENABLED=true` and a real `SECRET_KEY` in `.env` — mutating `/contracts` endpoints will then require a valid `logistics_manager` token; all `GET` endpoints stay open.

### 27.3 Rate limiting & request logging

- `settings.RATE_LIMIT_ENABLED` (default `True`) applies a fixed-window limit (`settings.RATE_LIMIT_DEFAULT`, default `120/minute`) per client IP across every route via `slowapi`'s middleware — no per-route decorators needed.
- Every request is logged (method, path, status, duration) via a custom `app.middleware("http")` hook in `app/main.py`.

---

## 28. Running the `recommendation/` Service Locally

The service defaults to SQLite and synchronous (non-Celery) task execution, so it needs no Docker stack to run standalone:

```bash
cd recommendation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8001
```

On startup, `init_db()` creates tables, seeds vessel classes/ports/commodities/trade lanes, seeds baseline model-registry champions, and seeds the default `logistics_manager` user — so `/docs` is immediately usable with no separate seed step.

```bash
curl localhost:8001/health
curl localhost:8001/health/db
```

**To run against Postgres + Celery/Redis** (matching the plan's production shape) instead of the SQLite/synchronous default, set in `.env` (or the environment):

```text
DATABASE_URL=postgresql://<user>:<pass>@<host>:5432/<db>
REDIS_URL=redis://<host>:6379/0
USE_CELERY=true
```

then run the API and a worker per queue:

```bash
uvicorn app.main:app --port 8001
celery -A app.worker.celery_app worker -Q training,solver --loglevel=info
```

### Run the tests

```bash
cd recommendation
PYTHONPATH=. pytest tests/ -q
```

`tests/test_phase5_api.py` exercises every Phase 5 router (auth, ports, vessels, scenarios, contracts, risk) plus `/docs` and the OpenAPI schema end-to-end against the seeded synthetic dataset — the Phase 5 acceptance check from the implementation plan.

---

## 29. Quick Reference — `recommendation/` Commands

```bash
# Setup
cd recommendation && pip install -r requirements.txt

# Run
uvicorn app.main:app --reload --port 8001

# Train a model
curl -X POST localhost:8001/api/forecasts/models/train \
  -d '{"trade_lane_ids": [1], "vessel_class_ids": [3]}' -H "Content-Type: application/json"

# Get a forecast
curl "localhost:8001/api/forecasts?trade_lane_id=1&vessel_class_id=3"

# Get a recommendation
curl -X POST localhost:8001/api/recommend -H "Content-Type: application/json" \
  -d '{"commodity":"coking_coal","cargo_qty_mt":75000,"destination_port_code":"INPRT","laycan_start":"2026-10-01","laycan_end":"2026-10-15"}'

# Log in (once AUTH_ENABLED=true)
curl -X POST localhost:8001/api/auth/token -d "username=logistics_manager&password=changeme123"

# Tests
PYTHONPATH=. pytest tests/ -q
```

---

## 30. Updated Phase Roadmap / Handoff

```text
Phase 1 (backend/)
  ↓ Project scaffolding, DB schema, reference data, synthetic history
Phase 2 (backend/)
  ↓ Ingestion, validation, data-quality logging, feature snapshots, training panel
Phase 3 (recommendation/)
  ↓ Quantile forecasting models, model registry, champion promotion, inference service
Phase 4 (recommendation/)
  ↓ Port/vessel feasibility, quick + MILP solvers, scenario simulation, risk engine
Phase 5 (recommendation/)
  ↓ Full REST API, auth, rate limiting — done, this document
Phase 6 (not started)
  ↓ Frontend dashboard — first needs the Section 24 single-vs-split-service decision
```

---

## 31. `recommendation/` Definition of Done (Phases 3–5)

- `pip install -r requirements.txt` succeeds and `uvicorn app.main:app` starts without a Docker stack.
- `/health` and `/health/db` succeed.
- `/docs` renders and `/api/openapi.json` lists every router in Section 27.1.
- `POST /forecasts/models/train` + `GET /forecasts` return a forecast, with graceful fallback when no model is trained yet.
- `POST /recommend` returns a full recommendation (vessel class, contract type, cost breakdown, risk flags, rationale) for a sample cargo request.
- `POST /scenarios/compare` and `GET /risk/{lane_id}` work standalone, independent of a full recommendation.
- `/contracts` supports create/read/update/cancel.
- `POST /auth/token` issues a JWT for the seeded `logistics_manager` account; flipping `AUTH_ENABLED=true` enforces it on mutating `/contracts` calls without blocking reads.
- `PYTHONPATH=. pytest tests/ -q` passes in full (32 tests as of Phase 5: 18 Phase 3/4 + 14 Phase 5).
